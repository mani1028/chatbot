import os
import json
import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify, render_template, current_app, session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database import db
from models import (
    Admin, Site, Plan, ClientConfig, BrandingSettings, Intent, IntentPhrase,
    ChatLog, UnansweredQuestion, Usage, Billing, Bot, Announcement, Integration
)
from models.client import Client
from models.end_user import EndUser
from models.platform_settings import AuditLog

# ---------------------------------------------------
# DEFINE BLUEPRINT EXACTLY ONCE
# ---------------------------------------------------
admin_api = Blueprint("admin_api", __name__)

# ---------------------------------------------------
# HELPERS & DECORATORS
# ---------------------------------------------------
def log_action(admin_id, site_id, action):
    log = AuditLog(admin_id=admin_id, site_id=site_id, action=action)
    db.session.add(log)
    db.session.commit()

def super_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("admin_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        admin = db.session.get(Admin, user_id)
        if not admin or not getattr(admin, "is_super", False):
            return jsonify({"error": "Super admin required"}), 403

        return func(*args, **kwargs)
    return wrapper

def client_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("client_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        client = db.session.get(Client, user_id)
        if not client:
            return jsonify({"error": "Client access required"}), 403

        return func(*args, **kwargs)
    return wrapper

def end_user_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401

        user = db.session.get(EndUser, user_id)
        if not user:
            return jsonify({"error": "End user access required"}), 403

        return func(*args, **kwargs)
    return wrapper

# ===================================================
# SUPER ADMIN ROUTES (Dashboard Core)
# ===================================================

@admin_api.route("/super/stats", methods=["GET"])
@super_admin_required
def super_stats():
    """Provides high-level KPI stats for the Super Admin Dashboard."""
    site_count = Site.query.count()
    total_chats = ChatLog.query.count()
    return jsonify({"site_count": site_count, "total_chats": total_chats})

@admin_api.route("/super/handoffs", methods=["GET"])
@super_admin_required
def super_handoffs():
    """Provides a global view of users waiting for a human agent."""
    logs = ChatLog.query.filter(ChatLog.detected_intent=='HUMAN').order_by(ChatLog.created_at.desc()).limit(20).all()
    handoffs = []
    for log in logs:
        site = db.session.get(Site, log.site_id) if log.site_id else None
        handoffs.append({
            "tenant_name": site.name if site else "Unknown",
            "session_id": log.session_id,
            "last_message": log.user_message or "Agent Requested",
        })
    return jsonify({"handoffs": handoffs})

@admin_api.route("/super/admins", methods=["GET"])
@super_admin_required
def list_all_admins():
    """Lists all Super Admins and Client Admins."""
    admins = Admin.query.all()
    admin_list = []
    for a in admins:
        admin_list.append({
            "id": a.id,
            "username": a.username,
            "site_id": getattr(a, 'site_id', None),
            "is_super": getattr(a, 'is_super', False),
            "created_at": "Active" 
        })
    return jsonify({"admins": admin_list})

@admin_api.route("/super/admins/<int:admin_id>", methods=["PUT"])
@super_admin_required
def update_admin(admin_id):
    data = request.json
    admin = db.session.get(Admin, admin_id)
    if not admin:
        return jsonify({"error": "Admin not found"}), 404
    if 'username' in data:
        admin.username = data['username']
    if 'password' in data and data['password']:
        admin.set_password(data['password'])
    db.session.commit()
    return jsonify({"success": True, "message": "Admin updated successfully"})

@admin_api.route("/super/settings", methods=["GET"])
@super_admin_required
def list_super_settings():
    """Mock route for Global Platform API keys."""
    return jsonify({"settings": [
        {"key": "OPENAI_API_KEY", "value": "********", "updated_at": "System Env"},
        {"key": "CRM_WEBHOOK_URL", "value": "Active", "updated_at": "System Env"}
    ]})

@admin_api.route("/super/settings", methods=["POST"])
@super_admin_required
def update_super_settings():
    """Update global platform settings (API keys, webhooks, etc)."""
    data = request.get_json()
    # Example: update settings in DB or env
    # For demo, just echo back
    updated = []
    for item in data.get("settings", []):
        updated.append({
            "key": item.get("key"),
            "value": item.get("value"),
            "updated_at": "Now"
        })
    return jsonify({"updated": updated, "success": True})

@admin_api.route("/super/health-check", methods=["GET"])
@super_admin_required
def system_health():
    db_path = os.path.join(os.getcwd(), 'chatbot', 'instance', 'chatbot.db')
    return jsonify({
        "database": {
            "exists": os.path.exists(db_path),
            "writable": os.access(db_path, os.W_OK) if os.path.exists(db_path) else False
        },
        "system": "Operational",
        "api_status": "Healthy"
    })

@admin_api.route("/super/audit-logs", methods=["GET"])
@super_admin_required
def load_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return jsonify({"logs": [{"timestamp": l.timestamp, "action": l.action, "admin_id": l.admin_id} for l in logs]})

@admin_api.route("/super/sites", methods=["GET"])
@super_admin_required
def list_sites():
    sites = Site.query.all()
    return jsonify({"sites": [s.to_dict() for s in sites]})

@admin_api.route("/super/sites", methods=["POST"])
@super_admin_required
def create_site():
    data = request.json or {}
    try:
        name = data.get("name", "").strip()
        domain = data.get("domain", "").strip()
        admin_username = data.get("admin_username", "").strip()
        admin_password = data.get("admin_password", "").strip()

        if not name or not admin_username or not admin_password:
            return jsonify({"error": "Missing required fields"}), 400

        if Admin.query.filter_by(username=admin_username).first():
            return jsonify({"error": "Admin username already exists"}), 400

        new_site = Site(name=name, domain=domain, status="active", bot_name=f"{name} Bot", plan_id=1)
        db.session.add(new_site)
        db.session.flush()

        # Create default Bot for the new site
        new_bot = Bot(site_id=new_site.id, name=f"{name} Primary Bot", status="active")
        db.session.add(new_bot)

        # Create initial Billing record for the new site
        new_billing = Billing(site_id=new_site.id, plan_id=1, amount=0.0, status="active", paid=True)
        db.session.add(new_billing)

        new_admin = Admin(username=admin_username, site_id=new_site.id, is_super=False)
        new_admin.set_password(admin_password)
        db.session.add(new_admin)
        db.session.commit()

        return jsonify({"success": True, "site": new_site.to_dict(), "admin_username": admin_username})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_api.route("/super/sites/<int:site_id>/status", methods=["PUT"])
@super_admin_required
def toggle_site_status(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    site.status = 'suspended' if site.status == 'active' else 'active'
    db.session.commit()
    return jsonify({"success": True, "new_status": site.status})

@admin_api.route("/super/sites/<int:site_id>/impersonate", methods=["POST"])
@super_admin_required
def impersonate_site(site_id):
    target_admin = Admin.query.filter_by(site_id=site_id, is_super=False).first()
    if not target_admin:
        return jsonify({"error": "No client admin found for this site"}), 404
    session["admin_id"] = target_admin.id
    session["site_id"] = site_id
    admin_id = session.get('real_admin_id') or session.get('admin_id')
    log_action(admin_id, site_id, f"IMPERSONATE_CLIENT_ADMIN (target_admin_id={target_admin.id})")
    return jsonify({"success": True, "redirect": "/admin/dashboard"})

@admin_api.route("/super/import_template", methods=["POST"])
@super_admin_required
def import_template():
    data = request.get_json()
    filename = data.get("filename")
    site_id = data.get("site_id")
    if not filename or not site_id:
        return jsonify({"error": "Missing filename or site_id"}), 400

    template_path = os.path.join(os.path.dirname(__file__), "..", "intent_templates", filename)
    if not os.path.exists(template_path):
        return jsonify({"error": "Template file not found"}), 404

    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        from services.importer import import_sector_template
        result = import_sector_template(site_id, json_data)
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- SUPER ADMIN: BOTS & BILLING ---
@admin_api.route("/super/bots", methods=["POST"])
@super_admin_required
def create_bot():
    data = request.get_json()
    site_id = data.get("site_id")
    name = data.get("name", "New Bot")
    status = data.get("status", "active")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    bot = Bot(site_id=site_id, name=name, status=status)
    db.session.add(bot)
    db.session.commit()
    return jsonify({"success": True, "bot": bot.to_dict()})

@admin_api.route("/super/billing", methods=["POST"])
@super_admin_required
def create_billing():
    data = request.get_json()
    site_id = data.get("site_id")
    plan_id = data.get("plan_id", 1)
    amount = float(data.get("amount", 0.0))
    status = data.get("status", "active")
    paid = bool(data.get("paid", True))
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    billing = Billing(site_id=site_id, plan_id=plan_id, amount=amount, status=status, paid=paid)
    db.session.add(billing)
    db.session.commit()
    return jsonify({"success": True, "billing": billing.to_dict()})
@admin_api.route("/super/bots", methods=["GET"])
@super_admin_required
def list_bots():
    bots = Bot.query.all()
    return jsonify({"bots": [b.to_dict() for b in bots]})

@admin_api.route("/super/bots/<int:bot_id>", methods=["DELETE"])
@super_admin_required
def delete_bot(bot_id):
    bot = Bot.query.get(bot_id)
    if bot:
        db.session.delete(bot)
        db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/billing", methods=["GET"])
@super_admin_required
def list_billing():
    records = Billing.query.all()
    return jsonify({"billing": [b.to_dict() for b in records]})

@admin_api.route("/super/billing/<int:billing_id>", methods=["DELETE"])
@super_admin_required
def delete_billing(billing_id):
    billing = Billing.query.get(billing_id)
    if billing:
        db.session.delete(billing)
        db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/plans", methods=["GET"])
@super_admin_required
def list_plans():
    plans = Plan.query.all()
    return jsonify({"plans": [p.to_dict() for p in plans]})

# --- Lead Capture Dashboard & Export ---
@admin_api.route("/super/leads", methods=["GET"])
@super_admin_required
def view_leads():
    """Returns all captured leads for dashboard view/export."""
    from models.lead_capture import LeadCapture
    leads = LeadCapture.query.order_by(LeadCapture.captured_at.desc()).limit(500).all()
    result = []
    for lead in leads:
        result.append({
            "id": lead.id,
            "name": lead.user_name,
            "email": lead.user_email,
            "phone": getattr(lead, 'user_phone', None),
            "question": lead.question_context,
            "session_id": lead.session_id,
            "captured_at": lead.captured_at.strftime('%Y-%m-%d %H:%M'),
        })
    return jsonify({"leads": result})

@admin_api.route("/super/leads/export", methods=["GET"])
@super_admin_required
def export_leads_csv():
    """Exports all leads as CSV for download."""
    from models.lead_capture import LeadCapture
    import csv
    from io import StringIO
    leads = LeadCapture.query.order_by(LeadCapture.captured_at.desc()).all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Name", "Email", "Phone", "Question", "Session ID", "Captured At"])
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.user_name,
            lead.user_email,
            getattr(lead, 'user_phone', ''),
            lead.question_context,
            lead.session_id,
            lead.captured_at.strftime('%Y-%m-%d %H:%M'),
        ])
    output = si.getvalue()
    return current_app.response_class(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=leads.csv"}
    )

# --- Booking Request Dashboard & Export ---
@admin_api.route("/super/bookings", methods=["GET"])
@super_admin_required
def view_bookings():
    """Returns all booking requests for dashboard view/export."""
    from models.booking_request import BookingRequest
    bookings = BookingRequest.query.order_by(BookingRequest.created_at.desc()).limit(500).all()
    result = []
    for booking in bookings:
        result.append({
            "id": booking.id,
            "name": booking.user_name,
            "email": booking.user_email,
            "phone": booking.user_phone,
            "date": booking.booking_date,
            "time": booking.booking_time,
            "message": booking.message,
            "session_id": booking.session_id,
            "created_at": booking.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return jsonify({"bookings": result})

@admin_api.route("/super/bookings/export", methods=["GET"])
@super_admin_required
def export_bookings_csv():
    """Exports all bookings as CSV for download."""
    from models.booking_request import BookingRequest
    import csv
    from io import StringIO
    bookings = BookingRequest.query.order_by(BookingRequest.created_at.desc()).all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["ID", "Name", "Email", "Phone", "Date", "Time", "Message", "Session ID", "Created At"])
    for booking in bookings:
        writer.writerow([
            booking.id,
            booking.user_name,
            booking.user_email,
            booking.user_phone,
            booking.booking_date,
            booking.booking_time,
            booking.message,
            booking.session_id,
            booking.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    output = si.getvalue()
    return current_app.response_class(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=bookings.csv"}
    )
# ===================================================
# CLIENT ADMIN ROUTES
# ===================================================

@admin_api.route("/client/stats", methods=["GET"])
def client_stats():
    site_id = session.get("site_id")
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    return jsonify({"status": site.status, "plan_name": site.plan.name if site.plan else "Free"})

@admin_api.route("/client/branding", methods=["GET", "POST"])
def client_branding():
    site_id = session.get("site_id") or request.args.get("site_id")
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()
    
    if request.method == "POST":
        data = request.json
        if not branding:
            branding = BrandingSettings(site_id=site_id)
            db.session.add(branding)
        for key in ['bot_name', 'initial_message', 'primary_color', 'theme_mode', 'position']:
            if key in data:
                setattr(branding, key, data[key])
        db.session.commit()
        return jsonify({"success": True})
        
    if branding:
        return jsonify({"branding": branding.to_dict()})
    return jsonify({"branding": {"bot_name": "Friday", "initial_message": "Hello!", "primary_color": "#6366f1", "theme_mode": "light", "position": "bottom-right"}})

@admin_api.route("/client/conversations", methods=["GET"])
def client_conversations():
    site_id = request.args.get("site_id") or session.get("site_id")
    logs = ChatLog.query.filter_by(site_id=site_id).order_by(ChatLog.created_at.desc()).limit(50).all()
    return jsonify({"conversations": [l.to_dict() for l in logs]})

@admin_api.route("/client/analytics", methods=["GET"])
def client_analytics():
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    
    total_messages = ChatLog.query.filter_by(site_id=site_id).count()
    success_count = ChatLog.query.filter(ChatLog.site_id==site_id, ChatLog.confidence >= 0.8).count()
    success_rate = round((success_count / total_messages * 100) if total_messages else 0, 1)

    trending = db.session.query(ChatLog.user_message, func.count(ChatLog.user_message))\
        .filter(ChatLog.site_id==site_id, ChatLog.user_message != '')\
        .group_by(ChatLog.user_message)\
        .order_by(func.count(ChatLog.user_message).desc())\
        .limit(5).all()
    
    failures = UnansweredQuestion.query.order_by(UnansweredQuestion.times_asked.desc()).limit(5).all()

    return jsonify({
        "ok": True,
        "total_messages": total_messages,
        "success_rate": success_rate,
        "trending_questions": [{'question': q, 'count': c} for q, c in trending],
        "failure_points": [{'question': f.question, 'count': f.times_asked} for f in failures]
    })

@admin_api.route("/client/leads", methods=["GET"])
def client_leads():
    site_id = request.args.get("site_id") or session.get("site_id")
    leads = ChatLog.query.filter_by(site_id=site_id, detected_intent='lead_capture').all()
    return jsonify({"leads": [l.to_dict() for l in leads]})

@admin_api.route("/client/config", methods=["GET", "POST"])
def client_config():
    site_id = request.args.get("site_id") or session.get("site_id")
    import re # Add this import at top

    if request.method == "POST":
        data = request.json
        for key, value in data.items():
            config = ClientConfig.query.filter_by(site_id=site_id, key=key).first()
            if config:
                config.value = value
            else:
                new_cfg = ClientConfig(site_id=site_id, key=key, value=value)
                db.session.add(new_cfg)
        db.session.commit()
        return jsonify({"success": True})

    configs = ClientConfig.query.filter_by(site_id=site_id).all()
    config_dict = {c.key: c.value for c in configs}
    
    active_intents = Intent.query.filter_by(site_id=site_id).all()
    required_keys = set()
    
    for intent in active_intents:
        # AUTO-DETECT: Find anything inside {curly_braces} in the response text
        if intent.response:
            found = re.findall(r'\{(.*?)\}', intent.response)
            for f in found:
                required_keys.add(f)
                
    return jsonify({"config": {k: config_dict.get(k, '') for k in required_keys}})

@admin_api.route("/client/intents", methods=["GET", "POST"])
def client_intents():
    site_id = request.args.get("site_id") or session.get("site_id")
    if request.method == "POST":
        data = request.json
        new_intent = Intent(
            site_id=site_id,
            intent_name=data.get("intent_name"),
            response=data.get("response"),
            intent_type=data.get("intent_type", "INFO"),
            confidence_threshold=0.7
        )
        db.session.add(new_intent)
        db.session.flush() 
        for p in data.get("phrases", []):
            if p:
                db.session.add(IntentPhrase(intent_id=new_intent.id, phrase=p))
        db.session.commit()
        return jsonify({"success": True})
        
    intents = Intent.query.filter_by(site_id=site_id).all()
    def intent_to_dict_full(i):
        d = i.to_dict() if hasattr(i, 'to_dict') else {}
        d['intent_type'] = getattr(i, 'intent_type', None)
        d['config_required'] = getattr(i, 'config_required', [])
        return d
    return jsonify({"intents": [intent_to_dict_full(i) for i in intents]})

# --- SUPER ADMIN: BLUEPRINTS ---
@admin_api.route("/super/template_files", methods=["GET"])
@super_admin_required
def list_template_files():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, "intent_templates")
        if not os.path.exists(template_dir):
            return jsonify({"files": []})
            
        files_data = []
        for f in os.listdir(template_dir):
            if f.endswith(".json"):
                filepath = os.path.join(template_dir, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file_obj:
                        data = json.load(file_obj)
                        intents = data.get("intents", [])
                        intent_preview = [{"name": i.get("intent_name"), "type": i.get("intent_type", "INFO")} for i in intents]
                        files_data.append({
                            "filename": f,
                            "template_name": data.get("template_name", f),
                            "description": data.get("description", "No description provided."),
                            "intent_count": len(intents),
                            "intents": intent_preview
                        })
                except Exception:
                    files_data.append({
                        "filename": f, "template_name": f, "description": "Invalid JSON format",
                        "intent_count": 0, "intents": []
                    })
        files_data = sorted(files_data, key=lambda x: x['filename'])
        return jsonify({"files": files_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_api.route("/client/intents/<int:intent_id>", methods=["PUT", "DELETE"])
def manage_client_intent(intent_id):
    site_id = request.args.get("site_id") or session.get("site_id")
    intent = Intent.query.filter_by(id=intent_id, site_id=site_id).first()
    if not intent:
        return jsonify({"error": "Not found"}), 404

    if request.method == "DELETE":
        IntentPhrase.query.filter_by(intent_id=intent.id).delete()
        db.session.delete(intent)
        db.session.commit()
        return jsonify({"success": True})

    if request.method == "PUT":
        data = request.json
        intent.intent_name = data.get("intent_name", intent.intent_name)
        intent.response = data.get("response", intent.response)
        intent.intent_type = data.get("intent_type", intent.intent_type)

        phrases = data.get("phrases")
        if phrases is not None:
            IntentPhrase.query.filter_by(intent_id=intent.id).delete()
            for p in phrases:
                if p:
                    db.session.add(IntentPhrase(intent_id=intent.id, phrase=p))

        db.session.commit()
        return jsonify({"success": True})