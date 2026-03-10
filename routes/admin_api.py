import os
import json
import re
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify, render_template, current_app, session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from database import db
from config import CONFIDENCE_THRESHOLD
from models import (
    Admin, Site, Plan, ClientConfig, BrandingSettings, Intent, IntentPhrase,
    ChatLog, UnansweredQuestion, Usage, Billing, Bot, Announcement, Integration, ContactRequest
)
from models.client import Client
from models.end_user import EndUser
from models.conversation import Conversation
from models.platform_settings import AuditLog

# Stage 2 imports
from models.conversation_state import ConversationState
from models.form import FormDefinition, FormSubmission
from models.webhook import WebhookConfig, WebhookLog
from services.feature_gate import get_site_features, require_feature, check_limit, FEATURE_ANALYTICS, FEATURE_FORMS, FEATURE_WEBHOOKS
from services.analytics_service import get_full_analytics, get_overview
from services.webhook_service import get_webhook_stats

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

    # THE FIX: Standardize template path using absolute path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "intent_templates", filename)
    
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

# --- ALIAS ROUTES (health / audit_logs) ---
@admin_api.route("/super/health", methods=["GET"])
@super_admin_required
def system_health_alias():
    """Alias for /super/health-check used by the frontend."""
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = "Online"
    except Exception:
        db_status = "Offline"
    return jsonify({
        "db_status": db_status,
        "system": "Operational",
        "api_status": "Healthy"
    })

@admin_api.route("/super/audit_logs", methods=["GET"])
@super_admin_required
def load_audit_logs_alias():
    """Alias for /super/audit-logs used by the frontend."""
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    admin_map = {}
    for l in logs:
        if l.admin_id not in admin_map:
            admin = db.session.get(Admin, l.admin_id)
            admin_map[l.admin_id] = admin.username if admin else f"Admin #{l.admin_id}"
    return jsonify({"logs": [{
        "id": l.id,
        "timestamp": l.timestamp.isoformat() if l.timestamp else '-',
        "created_at": l.timestamp.isoformat() if l.timestamp else '-',
        "action": l.action,
        "admin_id": l.admin_id,
        "admin_username": admin_map.get(l.admin_id, '-')
    } for l in logs]})

# --- SUPER ADMIN: GET SITE ---
@admin_api.route("/super/sites/<int:site_id>", methods=["GET"])
@super_admin_required
def get_site(site_id):
    """Get site details including assigned intents"""
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    
    # Get assigned intents for this site
    intents = Intent.query.filter_by(site_id=site_id).all()
    intents_data = []
    for intent in intents:
        intents_data.append({
            "id": intent.id,
            "intent_name": intent.intent_name,
            "intent_type": intent.intent_type,
            "sector": intent.sector,
            "response": intent.response,
            "template_file": intent.template_file,
            "created_at": intent.created_at.isoformat() if intent.created_at else None,
            "confidence_threshold": intent.confidence_threshold
        })
    
    return jsonify({
        "site": {
            "id": site.id,
            "name": site.name,
            "domain": site.domain,
            "plan_id": site.plan_id,
            "intents": intents_data
        }
    })

# --- SUPER ADMIN: EDIT SITE ---
@admin_api.route("/super/sites/<int:site_id>", methods=["PUT"])
@super_admin_required
def update_site(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    data = request.get_json()
    if 'name' in data:
        site.name = data['name']
    if 'domain' in data:
        site.domain = data['domain']
    if 'plan_id' in data:
        site.plan_id = int(data['plan_id'])
    db.session.commit()
    admin_id = session.get('admin_id')
    log_action(admin_id, site_id, f"UPDATE_SITE name={site.name}")
    return jsonify({"success": True, "site": site.to_dict()})

# --- SUPER ADMIN: PLATFORM ANALYTICS ---
@admin_api.route("/super/analytics", methods=["GET"])
@super_admin_required
def platform_analytics():
    """Platform-wide analytics for all tenants."""
    total_sites = Site.query.count()
    active_sites = Site.query.filter_by(status='active').count()
    suspended_sites = Site.query.filter_by(status='suspended').count()
    total_chats = ChatLog.query.count()
    total_bots = Bot.query.count()
    total_intents = Intent.query.count()
    total_plans = Plan.query.count()
    active_billing = Billing.query.filter_by(status='active').count()
    total_revenue = db.session.query(func.coalesce(func.sum(Billing.amount), 0)).filter_by(paid=True).scalar()

    # Top tenants by message count
    top_tenants = db.session.query(
        Site.id, Site.name, func.count(ChatLog.id).label('msg_count')
    ).outerjoin(ChatLog, ChatLog.site_id == Site.id)\
     .group_by(Site.id, Site.name)\
     .order_by(func.count(ChatLog.id).desc())\
     .limit(10).all()

    # Top intents across platform
    top_intents = db.session.query(
        ChatLog.detected_intent, func.count(ChatLog.id).label('count')
    ).filter(ChatLog.detected_intent != None, ChatLog.detected_intent != '')\
     .group_by(ChatLog.detected_intent)\
     .order_by(func.count(ChatLog.id).desc())\
     .limit(10).all()

    # Monthly chat volume (last 6 months)
    monthly_chats = db.session.query(
        func.strftime('%Y-%m', ChatLog.created_at).label('month'),
        func.count(ChatLog.id).label('count')
    ).group_by(func.strftime('%Y-%m', ChatLog.created_at))\
     .order_by(func.strftime('%Y-%m', ChatLog.created_at).desc())\
     .limit(6).all()

    return jsonify({
        "total_sites": total_sites,
        "active_sites": active_sites,
        "suspended_sites": suspended_sites,
        "total_chats": total_chats,
        "total_bots": total_bots,
        "total_intents": total_intents,
        "total_plans": total_plans,
        "active_billing": active_billing,
        "total_revenue": float(total_revenue or 0),
        "top_tenants": [{"id": t[0], "name": t[1], "messages": t[2]} for t in top_tenants],
        "top_intents": [{"intent": t[0], "count": t[1]} for t in top_intents],
        "monthly_chats": [{"month": m[0], "count": m[1]} for m in monthly_chats]
    })

# --- SUPER ADMIN: USAGE CRUD ---
@admin_api.route("/super/usage", methods=["GET"])
@super_admin_required
def list_usage():
    records = Usage.query.order_by(Usage.created_at.desc()).all()
    result = []
    for u in records:
        result.append({
            "id": u.id,
            "site_id": u.site_id,
            "bot_id": 0,
            "messages": u.messages,
            "period": u.month,
            "storage_mb": u.storage_mb,
            "api_calls": u.api_calls,
            "active_users": u.active_users
        })
    return jsonify({"usage": result})

@admin_api.route("/super/usage", methods=["POST"])
@super_admin_required
def create_usage():
    data = request.get_json()
    record = Usage(
        site_id=int(data.get("site_id", 0)),
        messages=int(data.get("messages", 0)),
        month=data.get("period", ""),
        storage_mb=float(data.get("storage_mb", 0)),
        api_calls=int(data.get("api_calls", 0)),
        active_users=int(data.get("active_users", 0))
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"success": True, "id": record.id})

@admin_api.route("/super/usage/<int:usage_id>", methods=["PUT"])
@super_admin_required
def update_usage(usage_id):
    record = db.session.get(Usage, usage_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if 'site_id' in data: record.site_id = int(data['site_id'])
    if 'messages' in data: record.messages = int(data['messages'])
    if 'period' in data: record.month = data['period']
    db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/usage/<int:usage_id>", methods=["DELETE"])
@super_admin_required
def delete_usage(usage_id):
    record = db.session.get(Usage, usage_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return jsonify({"success": True})

# --- SUPER ADMIN: INTEGRATIONS CRUD ---
@admin_api.route("/super/integrations", methods=["GET"])
@super_admin_required
def list_integrations():
    records = Integration.query.all()
    result = []
    for i in records:
        result.append({
            "id": i.id,
            "site_id": 0,
            "name": i.name,
            "type": i.type,
            "config": i.config or '',
            "status": 'active' if i.enabled else 'inactive'
        })
    return jsonify({"integrations": result})

@admin_api.route("/super/integrations", methods=["POST"])
@super_admin_required
def create_integration():
    data = request.get_json()
    record = Integration(
        name=data.get("type", "Integration"),
        type=data.get("type", ""),
        config=data.get("config", ""),
        enabled=data.get("status", "active") == "active"
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"success": True, "id": record.id})

@admin_api.route("/super/integrations/<int:integration_id>", methods=["PUT"])
@super_admin_required
def update_integration(integration_id):
    record = db.session.get(Integration, integration_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if 'type' in data: record.type = data['type']
    if 'config' in data: record.config = data['config']
    if 'name' in data: record.name = data['name']
    if 'status' in data: record.enabled = data['status'] == 'active'
    db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/integrations/<int:integration_id>", methods=["DELETE"])
@super_admin_required
def delete_integration(integration_id):
    record = db.session.get(Integration, integration_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return jsonify({"success": True})

# --- SUPER ADMIN: ANNOUNCEMENTS CRUD ---
@admin_api.route("/super/announcements", methods=["GET"])
@super_admin_required
def list_announcements():
    records = Announcement.query.order_by(Announcement.created_at.desc()).all()
    result = []
    for a in records:
        result.append({
            "id": a.id,
            "site_id": 0,
            "title": a.title,
            "message": a.message,
            "status": 'active' if a.visible else 'inactive',
            "created_at": a.created_at.isoformat() if a.created_at else None
        })
    return jsonify({"announcements": result})

@admin_api.route("/super/announcements", methods=["POST"])
@super_admin_required
def create_announcement():
    data = request.get_json()
    record = Announcement(
        title=data.get("title", ""),
        message=data.get("message", ""),
        visible=data.get("status", "active") == "active"
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"success": True, "id": record.id})

@admin_api.route("/super/announcements/<int:announcement_id>", methods=["PUT"])
@super_admin_required
def update_announcement(announcement_id):
    record = db.session.get(Announcement, announcement_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if 'title' in data: record.title = data['title']
    if 'message' in data: record.message = data['message']
    if 'status' in data: record.visible = data['status'] == 'active'
    db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/announcements/<int:announcement_id>", methods=["DELETE"])
@super_admin_required
def delete_announcement(announcement_id):
    record = db.session.get(Announcement, announcement_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return jsonify({"success": True})

# --- SUPER ADMIN: CONVERSATIONS ---
@admin_api.route("/super/conversations", methods=["GET"])
@super_admin_required
def list_conversations():
    records = Conversation.query.order_by(Conversation.started_at.desc()).limit(100).all()
    return jsonify({"conversations": [c.to_dict() for c in records]})

@admin_api.route("/super/conversations/<int:conversation_id>", methods=["DELETE"])
@super_admin_required
def delete_conversation(conversation_id):
    record = db.session.get(Conversation, conversation_id)
    if record:
        db.session.delete(record)
        db.session.commit()
    return jsonify({"success": True})

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
    """Optimized conversations endpoint with pagination & limit to latest only."""
    site_id = request.args.get("site_id") or session.get("site_id")
    limit = min(int(request.args.get("limit", 50)), 100)  # Cap limit at 100
    
    # Only fetch the columns we need, ordered descending for latest first
    logs = ChatLog.query.filter_by(site_id=site_id)\
        .order_by(ChatLog.created_at.desc())\
        .limit(limit)\
        .all()
    
    return jsonify({"conversations": [l.to_dict() for l in logs]})

@admin_api.route("/client/analytics", methods=["GET"])
def client_analytics():
    """Optimized analytics endpoint: single query with aggregations."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    
    # OPTIMIZATION: Combine count & success metrics in ONE query
    stats = db.session.query(
        func.count(ChatLog.id).label('total'),
        func.sum(func.cast(ChatLog.confidence >= 0.8, db.Integer)).label('success')
    ).filter(ChatLog.site_id == site_id).first()
    
    total_messages = stats.total or 0
    success_count = stats.success or 0
    success_rate = round((success_count / total_messages * 100) if total_messages else 0, 1)

    # Get trending questions (site-specific)
    trending = db.session.query(ChatLog.user_message, func.count(ChatLog.user_message).label('cnt'))\
        .filter(ChatLog.site_id == site_id, ChatLog.user_message != '')\
        .group_by(ChatLog.user_message)\
        .order_by(func.count(ChatLog.user_message).desc())\
        .limit(5).all()
    
    # Get failures (global, but could filter by site if needed)
    failures = UnansweredQuestion.query.order_by(UnansweredQuestion.times_asked.desc()).limit(5).all()

    return jsonify({
        "ok": True,
        "total_messages": total_messages,
        "success_rate": success_rate,
        "trending_questions": [{'question': q, 'count': cnt} for q, cnt in trending],
        "failure_points": [{'question': f.question, 'count': f.times_asked} for f in failures]
    })

@admin_api.route("/client/leads", methods=["GET"])
def client_leads():
    """Get captured leads for the current site with name, email, and phone (optimized with limit)."""
    from models.lead_capture import LeadCapture
    site_id = request.args.get("site_id") or session.get("site_id")
    limit = min(int(request.args.get("limit", 100)), 500)  # Cap at 500
    
    if not site_id:
        return jsonify({"leads": []})
    
    # OPTIMIZATION: Add limit and only fetch latest records
    leads = LeadCapture.query.filter_by(site_id=int(site_id))\
        .order_by(LeadCapture.captured_at.desc())\
        .limit(limit)\
        .all()
    
    result = []
    for lead in leads:
        result.append({
            'created_at': lead.captured_at.isoformat() if lead.captured_at else None,
            'lead_name': lead.user_name,
            'lead_email': lead.user_email,
            'lead_phone': lead.user_phone,
            'user_message': lead.question_context
        })
    
    return jsonify({"leads": result})

# Contact Request Endpoints
@admin_api.route("/client/contact-requests", methods=["GET"])
def client_contact_requests():
    """Get all contact requests for the current site."""
    from models.contact_request import ContactRequest
    site_id = request.args.get("site_id") or session.get("site_id")
    
    if not site_id:
        return jsonify({"contact_requests": []})
    
    # Get filter parameters
    status_filter = request.args.get("status")  # Filter by status (new, viewed, etc.)
    priority_filter = request.args.get("priority")  # Filter by priority
    
    query = ContactRequest.query.filter_by(site_id=int(site_id))
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    
    # Order by created_at descending (newest first)
    contact_requests = query.order_by(ContactRequest.created_at.desc()).all()
    
    result = []
    for cr in contact_requests:
        result.append(cr.to_dict())
    
    return jsonify({"contact_requests": result})

@admin_api.route("/client/contact-requests/<int:request_id>", methods=["GET", "PUT"])
def contact_request_detail(request_id):
    """Get or update a specific contact request."""
    from models.contact_request import ContactRequest
    site_id = request.args.get("site_id") or session.get("site_id")
    
    if not site_id:
        return jsonify({"error": "No site ID"}), 400
    
    contact_request = ContactRequest.query.filter_by(
        id=request_id,
        site_id=int(site_id)
    ).first()
    
    if not contact_request:
        return jsonify({"error": "Contact request not found"}), 404
    
    if request.method == "GET":
        return jsonify(contact_request.to_dict())
    
    # PUT request - update the contact request
    data = request.get_json() or {}
    
    # Allow updating status, admin_notes, and assigned_to
    if 'status' in data:
        contact_request.status = data['status']
    if 'admin_notes' in data:
        contact_request.admin_notes = data['admin_notes']
    if 'assigned_to' in data:
        contact_request.assigned_to = data['assigned_to']
    
    contact_request.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        return jsonify(contact_request.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_api.route("/client/contact-requests/stats", methods=["GET"])
def contact_request_stats():
    """Get statistics about contact requests."""
    from models.contact_request import ContactRequest
    from sqlalchemy import func
    site_id = request.args.get("site_id") or session.get("site_id")
    
    if not site_id:
        return jsonify({"stats": {}})
    
    site_id = int(site_id)
    
    # Count by status
    status_counts = db.session.query(
        ContactRequest.status,
        func.count(ContactRequest.id)
    ).filter_by(site_id=site_id).group_by(ContactRequest.status).all()
    
    # Count by priority
    priority_counts = db.session.query(
        ContactRequest.priority,
        func.count(ContactRequest.id)
    ).filter_by(site_id=site_id).group_by(ContactRequest.priority).all()
    
    total = ContactRequest.query.filter_by(site_id=site_id).count()
    
    return jsonify({
        "stats": {
            "total": total,
            "by_status": {status: count for status, count in status_counts},
            "by_priority": {priority: count for priority, count in priority_counts}
        }
    })

@admin_api.route("/client/contact-requests-dashboard", methods=["GET"])
def contact_requests_dashboard():
    """Serve the contact requests admin dashboard page."""
    return render_template('contact_requests_admin.html')

@admin_api.route("/client/contact-requests/<int:request_id>", methods=["DELETE"])
def delete_contact_request(request_id):
    """Delete a contact request."""
    from models.contact_request import ContactRequest
    site_id = request.args.get("site_id") or session.get("site_id")
    
    if not site_id:
        return jsonify({"error": "No site ID"}), 400
    
    contact_request = ContactRequest.query.filter_by(
        id=request_id,
        site_id=int(site_id)
    ).first()
    
    if not contact_request:
        return jsonify({"error": "Contact request not found"}), 404
    
    try:
        db.session.delete(contact_request)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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

@admin_api.route("/client/ai-settings", methods=["GET", "POST"])
def client_ai_settings():
    """Get/Set AI and chat behavior settings (preserve_chat_history, etc.)"""
    site_id = request.args.get("site_id") or session.get("site_id")
    
    if not site_id:
        return jsonify({"error": "No site ID"}), 400
    
    if request.method == "POST":
        data = request.get_json() or {}
        # Save all settings to ClientConfig
        for key, value in data.items():
            config = ClientConfig.query.filter_by(site_id=site_id, key=key).first()
            if config:
                config.value = value
            else:
                new_cfg = ClientConfig(site_id=site_id, key=key, value=value)
                db.session.add(new_cfg)
        db.session.commit()
        return jsonify({"success": True})
    
    # GET: Return all AI settings
    configs = ClientConfig.query.filter_by(site_id=site_id).all()
    settings = {c.key: c.value for c in configs}
    
    return jsonify({"settings": settings})

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
            confidence_threshold=CONFIDENCE_THRESHOLD
        )
        db.session.add(new_intent)
        db.session.flush() 
        for p in data.get("phrases", []):
            if p:
                db.session.add(IntentPhrase(intent_id=new_intent.id, phrase=p))
        db.session.commit()
        return jsonify({"success": True})
    
    # OPTIMIZATION: Use selectinload to avoid N+1 queries when accessing intent.phrases
    from sqlalchemy.orm import selectinload
    intents = Intent.query.filter_by(site_id=site_id)\
        .options(selectinload(Intent.phrases))\
        .all()
    
    def intent_to_dict_full(i):
        d = i.to_dict() if hasattr(i, 'to_dict') else {}
        d['intent_type'] = getattr(i, 'intent_type', None)
        d['template_file'] = getattr(i, 'template_file', None)
        d['created_at'] = i.created_at.isoformat() if hasattr(i, 'created_at') and i.created_at else None
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
                        # Handle both old and new intent formats
                        intent_preview = []
                        for i in intents:
                            intent_preview.append({
                                "name": i.get("intent_name") or i.get("tag", "unknown"),
                                "type": i.get("intent_type", "INFO")
                            })
                        files_data.append({
                            "filename": f,
                            "template_name": data.get("template_name", f.replace('.json', '').replace('_', ' ').title()),
                            "description": data.get("description", f"Template with {len(intents)} intents"),
                            "intent_count": len(intents),
                            "intents": intent_preview
                        })
                except Exception as e:
                    files_data.append({
                        "filename": f, 
                        "template_name": f.replace('.json', '').replace('_', ' ').title(), 
                        "description": "Invalid JSON format",
                        "intent_count": 0, 
                        "intents": []
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


# ===================================================
# STAGE 2: ANALYTICS DASHBOARD
# ===================================================

@admin_api.route("/super/analytics/full", methods=["GET"])
@super_admin_required
def super_full_analytics():
    """Full analytics for super admin (all sites or specific site)."""
    site_id = request.args.get("site_id", type=int)
    days = request.args.get("days", 30, type=int)
    if site_id:
        return jsonify(get_full_analytics(site_id, days))
    # Aggregate across all sites
    sites = Site.query.all()
    if not sites:
        return jsonify({"error": "No sites found"}), 404
    return jsonify(get_full_analytics(sites[0].id, days))


@admin_api.route("/client/analytics/full", methods=["GET"])
def client_full_analytics():
    """Full analytics dashboard for a client's site."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    site_id = int(site_id)

    allowed, err = require_feature(site_id, FEATURE_ANALYTICS)
    if not allowed:
        # Return basic overview even without analytics feature
        return jsonify({"overview": get_overview(site_id, 30), "upgrade_required": True, "message": err})

    days = request.args.get("days", 30, type=int)
    return jsonify(get_full_analytics(site_id, days))


# ===================================================
# STAGE 2: FEATURE GATES
# ===================================================

@admin_api.route("/client/features", methods=["GET"])
def client_features():
    """Get feature flags and limits for the client's plan."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    return jsonify(get_site_features(int(site_id)))


@admin_api.route("/site-features", methods=["GET"])
def site_features_public():
    """Public endpoint: Get site features by public_key (for widget)."""
    site_key = request.args.get("site_key")
    if not site_key:
        return jsonify({"error": "Missing site_key parameter"}), 400
    
    site = Site.query.filter_by(public_key=site_key).first()
    if not site:
        return jsonify({"error": "Invalid site_key"}), 404
    
    return jsonify(get_site_features(site.id))


@admin_api.route("/super/plans/<int:plan_id>/features", methods=["PUT"])
@super_admin_required
def update_plan_features(plan_id):
    """Update feature gates for a specific plan."""
    plan = db.session.get(Plan, plan_id)
    if not plan:
        return jsonify({"error": "Plan not found"}), 404

    data = request.json or {}
    feature_fields = [
        'ai_enabled', 'workflows_enabled', 'forms_enabled',
        'analytics_enabled', 'webhooks_enabled', 'custom_branding',
        'priority_support', 'max_forms', 'max_webhooks',
        'max_intents', 'max_monthly_chats'
    ]
    for field in feature_fields:
        if field in data:
            setattr(plan, field, data[field])

    db.session.commit()
    log_action(session.get('admin_id'), None, f'Updated plan features: {plan.name}')
    return jsonify({"success": True, "plan": plan.to_dict()})


# ===================================================
# STAGE 2: MULTI-STEP FORMS
# ===================================================

@admin_api.route("/client/forms", methods=["GET", "POST"])
def client_forms():
    """List or create form definitions for a site."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    site_id = int(site_id)

    if request.method == "POST":
        allowed, err = require_feature(site_id, FEATURE_FORMS)
        if not allowed:
            return jsonify({"error": err}), 403

        current_count = FormDefinition.query.filter_by(site_id=site_id).count()
        if not check_limit(site_id, 'max_forms', current_count):
            return jsonify({"error": "Form limit reached for your plan. Please upgrade."}), 403

        data = request.json or {}
        form = FormDefinition(
            site_id=site_id,
            intent_id=data.get('intent_id'),
            name=data.get('name', 'New Form'),
            description=data.get('description', ''),
            completion_message=data.get('completion_message', 'Thank you! Your information has been submitted.'),
            webhook_url=data.get('webhook_url'),
            save_as_lead=data.get('save_as_lead', True),
            is_active=data.get('is_active', True)
        )
        form.set_steps(data.get('steps', []))
        db.session.add(form)
        db.session.commit()
        return jsonify({"success": True, "form": form.to_dict()})

    forms = FormDefinition.query.filter_by(site_id=site_id).all()
    return jsonify({"forms": [f.to_dict() for f in forms]})


@admin_api.route("/client/forms/<int:form_id>", methods=["GET", "PUT", "DELETE"])
def manage_client_form(form_id):
    """Get, update, or delete a form definition."""
    site_id = request.args.get("site_id") or session.get("site_id")
    form = FormDefinition.query.filter_by(id=form_id, site_id=site_id).first()
    if not form:
        return jsonify({"error": "Form not found"}), 404

    if request.method == "GET":
        return jsonify({"form": form.to_dict()})

    if request.method == "DELETE":
        FormSubmission.query.filter_by(form_id=form.id).delete()
        db.session.delete(form)
        db.session.commit()
        return jsonify({"success": True})

    if request.method == "PUT":
        data = request.json or {}
        form.name = data.get('name', form.name)
        form.description = data.get('description', form.description)
        form.completion_message = data.get('completion_message', form.completion_message)
        form.webhook_url = data.get('webhook_url', form.webhook_url)
        form.save_as_lead = data.get('save_as_lead', form.save_as_lead)
        form.is_active = data.get('is_active', form.is_active)
        form.intent_id = data.get('intent_id', form.intent_id)
        if 'steps' in data:
            form.set_steps(data['steps'])
        db.session.commit()
        return jsonify({"success": True, "form": form.to_dict()})


@admin_api.route("/client/forms/<int:form_id>/submissions", methods=["GET"])
def form_submissions(form_id):
    """List submissions for a form."""
    site_id = request.args.get("site_id") or session.get("site_id")
    form = FormDefinition.query.filter_by(id=form_id, site_id=site_id).first()
    if not form:
        return jsonify({"error": "Form not found"}), 404

    subs = FormSubmission.query.filter_by(form_id=form_id).order_by(FormSubmission.created_at.desc()).limit(50).all()
    return jsonify({"submissions": [s.to_dict() for s in subs]})


# ===================================================
# STAGE 2: WEBHOOK MANAGEMENT
# ===================================================

@admin_api.route("/client/webhooks", methods=["GET", "POST"])
def client_webhooks():
    """List or create webhooks for a site."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    site_id = int(site_id)

    if request.method == "POST":
        allowed, err = require_feature(site_id, FEATURE_WEBHOOKS)
        if not allowed:
            return jsonify({"error": err}), 403

        current_count = WebhookConfig.query.filter_by(site_id=site_id).count()
        if not check_limit(site_id, 'max_webhooks', current_count):
            return jsonify({"error": "Webhook limit reached for your plan. Please upgrade."}), 403

        data = request.json or {}
        webhook = WebhookConfig(
            site_id=site_id,
            name=data.get('name', 'New Webhook'),
            event_type=data.get('event_type', 'handoff'),
            url=data.get('url', ''),
            method=data.get('method', 'POST'),
            max_retries=data.get('max_retries', 3),
            timeout_seconds=data.get('timeout_seconds', 10),
            enabled=data.get('enabled', True),
            payload_template=data.get('payload_template')
        )
        if data.get('headers'):
            webhook.set_headers(data['headers'])
        db.session.add(webhook)
        db.session.commit()
        return jsonify({"success": True, "webhook": webhook.to_dict()})

    webhooks = WebhookConfig.query.filter_by(site_id=site_id).all()
    return jsonify({"webhooks": [w.to_dict() for w in webhooks]})


@admin_api.route("/client/webhooks/<int:webhook_id>", methods=["GET", "PUT", "DELETE"])
def manage_client_webhook(webhook_id):
    """Get, update, or delete a webhook."""
    site_id = request.args.get("site_id") or session.get("site_id")
    webhook = WebhookConfig.query.filter_by(id=webhook_id, site_id=site_id).first()
    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    if request.method == "GET":
        return jsonify({"webhook": webhook.to_dict()})

    if request.method == "DELETE":
        WebhookLog.query.filter_by(webhook_id=webhook.id).delete()
        db.session.delete(webhook)
        db.session.commit()
        return jsonify({"success": True})

    if request.method == "PUT":
        data = request.json or {}
        webhook.name = data.get('name', webhook.name)
        webhook.event_type = data.get('event_type', webhook.event_type)
        webhook.url = data.get('url', webhook.url)
        webhook.method = data.get('method', webhook.method)
        webhook.max_retries = data.get('max_retries', webhook.max_retries)
        webhook.timeout_seconds = data.get('timeout_seconds', webhook.timeout_seconds)
        webhook.enabled = data.get('enabled', webhook.enabled)
        webhook.payload_template = data.get('payload_template', webhook.payload_template)
        if 'headers' in data:
            webhook.set_headers(data['headers'])
        db.session.commit()
        return jsonify({"success": True, "webhook": webhook.to_dict()})


@admin_api.route("/client/webhooks/<int:webhook_id>/logs", methods=["GET"])
def webhook_logs(webhook_id):
    """View delivery logs for a webhook."""
    site_id = request.args.get("site_id") or session.get("site_id")
    webhook = WebhookConfig.query.filter_by(id=webhook_id, site_id=site_id).first()
    if not webhook:
        return jsonify({"error": "Webhook not found"}), 404

    logs = WebhookLog.query.filter_by(webhook_id=webhook_id).order_by(WebhookLog.created_at.desc()).limit(50).all()
    return jsonify({"logs": [l.to_dict() for l in logs]})


@admin_api.route("/client/webhooks/stats", methods=["GET"])
def client_webhook_stats():
    """Get webhook delivery stats for a site."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400
    return jsonify(get_webhook_stats(int(site_id)))


# ===================================================
# STAGE 2: CONVERSATION STATE (admin visibility)
# ===================================================

@admin_api.route("/client/sessions", methods=["GET"])
def client_active_sessions():
    """List active conversation states for a site."""
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "Missing site_id"}), 400

    states = ConversationState.query.filter_by(site_id=int(site_id))\
        .order_by(ConversationState.updated_at.desc()).limit(50).all()
    return jsonify({"sessions": [s.to_dict() for s in states]})


@admin_api.route("/client/sessions/<session_id>", methods=["GET"])
def client_session_detail(session_id):
    """Get conversation state for a specific session."""
    site_id = request.args.get("site_id") or session.get("site_id")
    state = ConversationState.query.filter_by(
        site_id=int(site_id), session_id=session_id
    ).first()
    if not state:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({"session": state.to_dict()})


# ===================================================
# SUPER ADMIN: INTENT ASSIGNMENT MANAGEMENT
# ===================================================

@admin_api.route("/super/blueprints", methods=["GET"])
@super_admin_required
def get_blueprint_intents():
    """Get all available blueprint intents (global intents with site_id=0)"""
    blueprints = Intent.query.filter_by(site_id=0).all()
    
    bp_list = []
    for bp in blueprints:
        bp_list.append({
            "id": bp.id,
            "name": bp.intent_name,
            "intent_type": bp.intent_type,
            "category": bp.sector,
            "phrases": [p.phrase for p in bp.phrases.all()],
            "response": bp.response[:100] if bp.response else "",
            "template_file": bp.template_file or "default"
        })
    
    # Also return grouped format for reference
    grouped = {}
    for bp in bp_list:
        template = bp["template_file"]
        if template not in grouped:
            grouped[template] = []
        grouped[template].append(bp)
    
    return jsonify({
        "blueprints": bp_list,
        "grouped": [
            {
                "template_file": template,
                "intent_count": len(intents),
                "intents": intents
            }
            for template, intents in grouped.items()
        ]
    })


@admin_api.route("/super/blueprints/<int:blueprint_id>", methods=["GET"])
@super_admin_required
def get_blueprint_detail(blueprint_id):
    """Get full details of a single blueprint intent"""
    blueprint = Intent.query.filter_by(id=blueprint_id, site_id=0).first()
    if not blueprint:
        return jsonify({"error": "Blueprint not found"}), 404
    
    return jsonify({
        "blueprint": {
            "id": blueprint.id,
            "name": blueprint.intent_name,
            "intent_type": blueprint.intent_type,
            "sector": blueprint.sector,
            "phrases": [p.phrase for p in blueprint.phrases.all()],
            "response": blueprint.response,
            "confidence_threshold": blueprint.confidence_threshold
        }
    }), 200


@admin_api.route("/super/sites/<int:site_id>/intents", methods=["GET"])
@super_admin_required
def super_get_site_intents(site_id):
    """Get all intents assigned to a specific site"""
    intents = Intent.query.filter_by(site_id=site_id).all()
    intents_list = [
        {
            "id": intent.id, 
            "intent_name": intent.intent_name,
            "intent_type": intent.intent_type,
            "phrase_count": intent.phrases.count(),
            "response": intent.response[:100] if intent.response else ""
        }
        for intent in intents
    ]
    return jsonify({"intents": intents_list})


@admin_api.route("/super/sites/<int:site_id>/assign-intent", methods=["POST"])
@super_admin_required
def super_assign_intent_to_site(site_id):
    """Assign a blueprint intent to a client site"""
    from models.intent import IntentPhrase
    
    data = request.get_json() or {}
    blueprint_id = data.get('blueprint_id')
    
    # Support both old (blueprint_id) and new (intent_name) formats
    if blueprint_id:
        # OLD FORMAT: Get blueprint from database
        blueprint = Intent.query.filter_by(id=blueprint_id, site_id=0).first()
        if not blueprint:
            return jsonify({"error": "Blueprint intent not found"}), 404
        
        intent_name = blueprint.intent_name
        intent_type = blueprint.intent_type
        sector = blueprint.sector
        confidence = blueprint.confidence
        confidence_threshold = blueprint.confidence_threshold
        response = blueprint.response
        phrases = [p.phrase for p in blueprint.phrases.all()]
    else:
        # NEW FORMAT: Use provided intent data (from JSON upload)
        intent_name = data.get('intent_name')
        intent_type = data.get('intent_type', 'info')
        sector = data.get('sector', 'general')
        confidence = data.get('confidence', 0.8)
        confidence_threshold = data.get('confidence_threshold', CONFIDENCE_THRESHOLD)
        response = data.get('response')
        phrases = data.get('phrases', [])
        template_file = data.get('template_file')  # NEW: Capture template file name
        
        if not intent_name:
            return jsonify({"error": "intent_name is required"}), 400
    
    # Check if intent already assigned to this site
    existing = Intent.query.filter_by(site_id=site_id, intent_name=intent_name).first()
    if existing:
        return jsonify({"error": f"Intent '{intent_name}' already assigned to this site"}), 409
    
    try:
        # Create a new intent for this site
        new_intent = Intent(
            site_id=site_id,
            intent_name=intent_name,
            intent_type=intent_type,
            sector=sector,
            confidence=confidence,
            confidence_threshold=confidence_threshold,
            response=response,
            template_file=template_file  # NEW: Store source template file
        )
        db.session.add(new_intent)
        db.session.flush()  # Get the new intent ID
        
        # Add phrases
        for phrase in phrases:
            new_phrase = IntentPhrase(intent_id=new_intent.id, phrase=phrase)
            db.session.add(new_phrase)
        
        db.session.commit()
        return jsonify({
            "success": True,
            "message": f"Intent '{intent_name}' assigned to site {site_id}",
            "intent": {
                "id": new_intent.id,
                "intent_name": new_intent.intent_name,
                "intent_type": new_intent.intent_type
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to assign intent: {str(e)}"}), 500


@admin_api.route("/super/sites/<int:site_id>/intents/<intent_name>", methods=["DELETE"])
@super_admin_required
def super_remove_intent_from_site(site_id, intent_name):
    """Remove an intent from a client site"""
    intent = Intent.query.filter_by(site_id=site_id, intent_name=intent_name).first()
    
    if not intent:
        return jsonify({"error": "Intent not found for this site"}), 404
    
    try:
        from models.intent import IntentPhrase
        # Delete associated phrases
        IntentPhrase.query.filter_by(intent_id=intent.id).delete()
        
        # Delete the intent
        db.session.delete(intent)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Intent '{intent_name}' removed from site {site_id}"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to remove intent: {str(e)}"}), 500


# ===================================================
# BLUEPRINT CRUD OPERATIONS (Create/Edit/Delete)
# ===================================================

@admin_api.route("/super/blueprints", methods=["POST"])
@super_admin_required
def create_blueprint():
    """Create a new blueprint intent (site_id=0)"""
    from models.intent import IntentPhrase
    
    data = request.get_json() or {}
    intent_name = data.get('intent_name', '').strip()
    response = data.get('response', '').strip()
    phrases = data.get('phrases', [])
    intent_type = data.get('intent_type', 'info')
    sector = data.get('sector', '')
    
    if not intent_name:
        return jsonify({"error": "intent_name is required"}), 400
    if not response:
        return jsonify({"error": "response is required"}), 400
    if not phrases or len(phrases) == 0:
        return jsonify({"error": "At least one phrase is required"}), 400
    
    # Check if blueprint with same name already exists
    existing = Intent.query.filter_by(site_id=0, intent_name=intent_name).first()
    if existing:
        return jsonify({"error": f"Blueprint '{intent_name}' already exists"}), 409
    
    try:
        # Create new blueprint intent
        new_blueprint = Intent(
            site_id=0,  # site_id=0 marks it as a global blueprint
            intent_name=intent_name,
            intent_type=intent_type,
            response=response,
            sector=sector,
            confidence_threshold=data.get('confidence_threshold', CONFIDENCE_THRESHOLD)
        )
        db.session.add(new_blueprint)
        db.session.flush()  # Get the new intent ID
        
        # Add phrases
        valid_phrases = []
        for phrase in phrases:
            phrase = (phrase or '').strip()
            if phrase:
                phrase_obj = IntentPhrase(intent_id=new_blueprint.id, phrase=phrase)
                db.session.add(phrase_obj)
                valid_phrases.append(phrase)
        
        if not valid_phrases:
            db.session.rollback()
            return jsonify({"error": "No valid phrases provided"}), 400
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Blueprint '{intent_name}' created successfully",
            "blueprint": {
                "id": new_blueprint.id,
                "name": new_blueprint.intent_name,
                "intent_type": new_blueprint.intent_type,
                "sector": new_blueprint.sector,
                "phrases": valid_phrases,
                "response": new_blueprint.response
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to create blueprint: {str(e)}"}), 500


@admin_api.route("/super/blueprints/<int:blueprint_id>", methods=["PUT"])
@super_admin_required
def update_blueprint(blueprint_id):
    """Update an existing blueprint intent"""
    from models.intent import IntentPhrase
    
    # Get the blueprint (must have site_id=0)
    blueprint = Intent.query.filter_by(id=blueprint_id, site_id=0).first()
    if not blueprint:
        return jsonify({"error": "Blueprint not found"}), 404
    
    data = request.get_json() or {}
    
    try:
        # Update basic fields
        if 'intent_name' in data:
            new_name = data['intent_name'].strip()
            if new_name and new_name != blueprint.intent_name:
                existing = Intent.query.filter_by(site_id=0, intent_name=new_name).first()
                if existing:
                    return jsonify({"error": f"Blueprint '{new_name}' already exists"}), 409
                blueprint.intent_name = new_name
        
        if 'response' in data:
            blueprint.response = data['response'].strip()
        
        if 'intent_type' in data:
            blueprint.intent_type = data['intent_type']
        
        if 'sector' in data:
            blueprint.sector = data['sector'].strip()
        
        if 'confidence_threshold' in data:
            blueprint.confidence_threshold = data['confidence_threshold']
        
        # Update phrases if provided
        if 'phrases' in data:
            phrases = data['phrases']
            if not phrases or len(phrases) == 0:
                return jsonify({"error": "At least one phrase is required"}), 400
            
            # Delete old phrases
            IntentPhrase.query.filter_by(intent_id=blueprint.id).delete()
            
            # Add new phrases
            for phrase in phrases:
                phrase = (phrase or '').strip()
                if phrase:
                    phrase_obj = IntentPhrase(intent_id=blueprint.id, phrase=phrase)
                    db.session.add(phrase_obj)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Blueprint '{blueprint.intent_name}' updated successfully",
            "blueprint": {
                "id": blueprint.id,
                "name": blueprint.intent_name,
                "intent_type": blueprint.intent_type,
                "sector": blueprint.sector,
                "phrases": [p.phrase for p in blueprint.phrases.all()],
                "response": blueprint.response
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update blueprint: {str(e)}"}), 500


@admin_api.route("/super/blueprints/<int:blueprint_id>", methods=["DELETE"])
@super_admin_required
def delete_blueprint(blueprint_id):
    """Delete a blueprint intent"""
    from models.intent import IntentPhrase
    
    # Get the blueprint (must have site_id=0)
    blueprint = Intent.query.filter_by(id=blueprint_id, site_id=0).first()
    if not blueprint:
        return jsonify({"error": "Blueprint not found"}), 404
    
    try:
        blueprint_name = blueprint.intent_name
        
        # Delete associated phrases
        IntentPhrase.query.filter_by(intent_id=blueprint.id).delete()
        
        # Delete the blueprint
        db.session.delete(blueprint)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Blueprint '{blueprint_name}' deleted successfully"
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete blueprint: {str(e)}"}), 500


# ---------------------------------------------------
# INTENT TEMPLATES MANAGEMENT
# ---------------------------------------------------
def admin_required(func):
    """Admin or super admin required"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("admin_id")
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        admin = db.session.get(Admin, user_id)
        if not admin:
            return jsonify({"error": "Admin not found"}), 404
        return func(*args, **kwargs)
    return wrapper


# UNIFIED PATH LOGIC: Ensures all routes look at the exact same physical folder
def get_templates_dir():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "intent_templates")
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir


@admin_api.route("/intent-templates", methods=["GET"])
@admin_required
def get_intent_templates():
    """List all intent template files"""
    templates_dir = get_templates_dir()
    
    templates = []
    try:
        for filename in os.listdir(templates_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(templates_dir, filename)
                file_size = os.path.getsize(file_path)
                file_time = os.path.getmtime(file_path)
                
                # Try to read file to get intent count
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        intent_count = len(data.get('intents', []))
                except:
                    intent_count = 0
                
                templates.append({
                    "filename": filename,
                    "size": file_size,
                    "modified": datetime.fromtimestamp(file_time).isoformat(),
                    "intents": intent_count
                })
        
        templates.sort(key=lambda x: x['modified'], reverse=True)
        return jsonify({"templates": templates}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_api.route("/intent-templates", methods=["POST"])
@admin_required
def upload_intent_template():
    """Upload a new intent template file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only .json files allowed"}), 400
    
    try:
        # Read and validate JSON
        file_content = file.read().decode('utf-8')
        json_data = json.loads(file_content)
        
        # Validate structure
        if 'intents' not in json_data or not isinstance(json_data['intents'], list):
            return jsonify({"error": "Invalid format: must contain 'intents' array"}), 400
        
        # Save file
        templates_dir = get_templates_dir()
        
        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(templates_dir, filename)
        
        # Check if file exists and prevent overwrite without confirmation
        if os.path.exists(file_path):
            return jsonify({
                "error": "File already exists",
                "exists": True,
                "filename": filename
            }), 409
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)
        
        intent_count = len(json_data['intents'])
        return jsonify({
            "success": True,
            "message": f"Template uploaded: {filename} ({intent_count} intents)",
            "filename": filename,
            "intents": intent_count
        }), 201
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@admin_api.route("/intent-templates/<filename>", methods=["GET"])
@admin_required
def download_intent_template(filename):
    """Download a template file"""
    from flask import send_from_directory
    templates_dir = get_templates_dir()
    file_path = os.path.join(templates_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(templates_dir, filename, as_attachment=True)


@admin_api.route("/intent-templates/<filename>", methods=["DELETE"])
@admin_required
def delete_intent_template(filename):
    """Delete a template file"""
    templates_dir = get_templates_dir()
    file_path = os.path.join(templates_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        os.remove(file_path)
        return jsonify({"success": True, "message": f"Template '{filename}' deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to delete: {str(e)}"}), 500


@admin_api.route("/intent-templates/<filename>/import", methods=["POST"])
@admin_required
def import_intent_template(filename):
    """Import a template into the current site"""
    user_id = session.get("admin_id")
    admin = db.session.get(Admin, user_id)
    site_id = admin.site_id
    
    templates_dir = get_templates_dir()
    file_path = os.path.join(templates_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Template file not found"}), 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        from services.importer import import_sector_template
        result = import_sector_template(site_id, template_data)
        
        if result.get('success'):
            return jsonify({"success": True, "message": result.get('message')}), 200
        else:
            return jsonify({"error": result.get('message')}), 400
    except Exception as e:
        return jsonify({"error": f"Import failed: {str(e)}"}), 500


# --- CLIENT: CHANNELS ---
@admin_api.route("/client/channels", methods=["GET"])
def get_client_channels():
    """Get all channels (integrations) for the current site"""
    site_id = session.get("site_id")
    if not site_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get channels (integrations) - current Integration model is global
    # For now, return available integration types
    integrations = Integration.query.all()
    channels = []
    for integration in integrations:
        channels.append({
            "id": integration.id,
            "name": integration.name,
            "type": integration.type,
            "enabled": integration.enabled
        })
    
    return jsonify({"channels": channels})


@admin_api.route("/client/channels", methods=["POST"])
def create_client_channel():
    """Create a new channel for the site"""
    site_id = session.get("site_id")
    if not site_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    data = request.get_json()
    name = data.get("name")
    channel_type = data.get("type")
    
    if not name or not channel_type:
        return jsonify({"error": "Name and type are required"}), 400
    
    new_channel = Integration(
        site_id=site_id,
        name=name,
        integration_type=channel_type,
        is_active=True
    )
    db.session.add(new_channel)
    db.session.commit()
    
    return jsonify({"success": True, "id": new_channel.id}), 201


# --- CLIENT: USAGE ---
@admin_api.route("/client/usage", methods=["GET"])
def get_client_usage():
    """Get usage statistics for the current site"""
    site_id = session.get("site_id")
    if not site_id:
        return jsonify({"error": "Not authenticated"}), 401
    
    # Get total messages
    total_messages = ChatLog.query.filter_by(site_id=site_id).count()
    
    # Get this month's messages
    from datetime import datetime
    current_month = datetime.utcnow().strftime('%Y-%m')
    usage_record = Usage.query.filter_by(site_id=site_id, month=current_month).first()
    messages_this_month = usage_record.messages if usage_record else 0
    
    # Mock API calls and storage (can be enhanced)
    api_calls = ChatLog.query.filter_by(site_id=site_id).count()
    storage_used = "0 MB"
    
    return jsonify({
        "total_messages": total_messages,
        "messages_this_month": messages_this_month,
        "api_calls": api_calls,
        "storage_used": storage_used,
        "usage_breakdown": {
            "labels": ["Messages", "API Calls", "Storage"],
            "data": [messages_this_month, api_calls, 0]
        }
    })


# ===== PHASE 1: FALLBACK REDUCTION - UNKNOWN INTENT MAPPING =====
# Routes for unknown intent management are now in routes/unknown_intent_admin.py
# Accessed at: /admin/api/unknown/*
