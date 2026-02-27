# --- Helper: Audit Logging ---
def log_action(admin_id, site_id, action):
    log = AuditLog(admin_id=admin_id, site_id=site_id, action=action)
    db.session.add(log)
    db.session.commit()

from models.chat_log import ChatLog
from flask import Blueprint, request, jsonify, session
from functools import wraps
import os
import json
from models import (
    Admin, Site, Plan, ClientConfig, BrandingSettings, Intent, IntentPhrase
)
from database import db
# Correct AuditLog import
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from models.platform_settings import AuditLog
# DEFINE BLUEPRINT FIRST (VERY IMPORTANT)
# ---------------------------------------------------
admin_api = Blueprint("admin_api", __name__)


# ---------------------------------------------------
# SUPER ADMIN DECORATOR
# ---------------------------------------------------
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

# --- Super Admin: Notifications/Announcements Management ---
from models.announcement import Announcement

@admin_api.route("/super/announcements", methods=["GET"])
@super_admin_required
def list_announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return jsonify({"announcements": [a.to_dict() for a in announcements]})

@admin_api.route("/super/announcements", methods=["POST"])
@super_admin_required
def create_announcement():
    data = request.json
    announcement = Announcement(
        title=data["title"],
        message=data["message"],
        visible=data.get("visible", True)
    )
    db.session.add(announcement)
    db.session.commit()
    return jsonify({"success": True, "announcement": announcement.to_dict()})

@admin_api.route("/super/announcements/<int:announcement_id>", methods=["PUT"])
@super_admin_required
def update_announcement(announcement_id):
    data = request.json
    announcement = Announcement.query.get(announcement_id)
    if not announcement:
        return jsonify({"error": "Announcement not found"}), 404
    for field in ["title", "message", "visible"]:
        if field in data:
            setattr(announcement, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "announcement": announcement.to_dict()})

@admin_api.route("/super/announcements/<int:announcement_id>", methods=["DELETE"])
@super_admin_required
def delete_announcement(announcement_id):
    announcement = Announcement.query.get(announcement_id)
    if not announcement:
        return jsonify({"error": "Announcement not found"}), 404
    db.session.delete(announcement)
    db.session.commit()
    return jsonify({"success": True})
# --- Super Admin: Integrations Management ---
from models.integration import Integration

@admin_api.route("/super/integrations", methods=["GET"])
@super_admin_required
def list_integrations():
    integrations = Integration.query.all()
    return jsonify({"integrations": [i.to_dict() for i in integrations]})

@admin_api.route("/super/integrations", methods=["POST"])
@super_admin_required
def create_integration():
    data = request.json
    integration = Integration(
        name=data["name"],
        type=data["type"],
        config=data.get("config", ""),
        enabled=data.get("enabled", True)
    )
    db.session.add(integration)
    db.session.commit()
    return jsonify({"success": True, "integration": integration.to_dict()})

@admin_api.route("/super/integrations/<int:integration_id>", methods=["PUT"])
@super_admin_required
def update_integration(integration_id):
    data = request.json
    integration = Integration.query.get(integration_id)
    if not integration:
        return jsonify({"error": "Integration not found"}), 404
    for field in ["name", "type", "config", "enabled"]:
        if field in data:
            setattr(integration, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "integration": integration.to_dict()})

@admin_api.route("/super/integrations/<int:integration_id>", methods=["DELETE"])
@super_admin_required
def delete_integration(integration_id):
    integration = Integration.query.get(integration_id)
    if not integration:
        return jsonify({"error": "Integration not found"}), 404
    db.session.delete(integration)
    db.session.commit()
    return jsonify({"success": True})
# --- Super Admin: Global Conversations Viewer ---
from models.conversation import Conversation

@admin_api.route("/super/conversations", methods=["GET"])
@super_admin_required
def list_conversations():
    conversations = Conversation.query.all()
    return jsonify({"conversations": [c.to_dict() for c in conversations]})

@admin_api.route("/super/conversations/<int:conv_id>", methods=["GET"])
@super_admin_required
def get_conversation(conv_id):
    conv = Conversation.query.get(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({"conversation": conv.to_dict()})

@admin_api.route("/super/conversations/<int:conv_id>", methods=["DELETE"])
@super_admin_required
def delete_conversation(conv_id):
    conv = Conversation.query.get(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"success": True})
# --- Super Admin: Usage & Quotas Management ---
from models.usage import Usage

@admin_api.route("/super/usage", methods=["GET"])
@super_admin_required
def list_usage():
    records = Usage.query.all()
    return jsonify({"usage": [u.to_dict() for u in records]})

@admin_api.route("/super/usage", methods=["POST"])
@super_admin_required
def create_usage():
    data = request.json
    usage = Usage(
        site_id=data["site_id"],
        messages=data.get("messages", 0),
        storage_mb=data.get("storage_mb", 0),
        api_calls=data.get("api_calls", 0),
        active_users=data.get("active_users", 0),
        month=data["month"]
    )
    db.session.add(usage)
    db.session.commit()
    return jsonify({"success": True, "usage": usage.to_dict()})

@admin_api.route("/super/usage/<int:usage_id>", methods=["PUT"])
@super_admin_required
def update_usage(usage_id):
    data = request.json
    usage = Usage.query.get(usage_id)
    if not usage:
        return jsonify({"error": "Usage record not found"}), 404
    for field in ["messages", "storage_mb", "api_calls", "active_users", "month"]:
        if field in data:
            setattr(usage, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "usage": usage.to_dict()})

@admin_api.route("/super/usage/<int:usage_id>", methods=["DELETE"])
@super_admin_required
def delete_usage(usage_id):
    usage = Usage.query.get(usage_id)
    if not usage:
        return jsonify({"error": "Usage record not found"}), 404
    db.session.delete(usage)
    db.session.commit()
    return jsonify({"success": True})
# --- Super Admin: Billing/Subscriptions Management ---
from models.billing import Billing

@admin_api.route("/super/billing", methods=["GET"])
@super_admin_required
def list_billing():
    records = Billing.query.all()
    return jsonify({"billing": [b.to_dict() for b in records]})

@admin_api.route("/super/billing", methods=["POST"])
@super_admin_required
def create_billing():
    data = request.json
    billing = Billing(
        site_id=data["site_id"],
        plan_id=data["plan_id"],
        status=data.get("status", "active"),
        amount=data["amount"],
        paid=data.get("paid", False),
        due_date=data.get("due_date")
    )
    db.session.add(billing)
    db.session.commit()
    return jsonify({"success": True, "billing": billing.to_dict()})

@admin_api.route("/super/billing/<int:billing_id>", methods=["PUT"])
@super_admin_required
def update_billing(billing_id):
    data = request.json
    billing = Billing.query.get(billing_id)
    if not billing:
        return jsonify({"error": "Billing record not found"}), 404
    for field in ["status", "amount", "paid", "due_date", "plan_id"]:
        if field in data:
            setattr(billing, field, data[field])
    db.session.commit()
    return jsonify({"success": True, "billing": billing.to_dict()})

@admin_api.route("/super/billing/<int:billing_id>", methods=["DELETE"])
@super_admin_required
def delete_billing(billing_id):
    billing = Billing.query.get(billing_id)
    if not billing:
        return jsonify({"error": "Billing record not found"}), 404
    db.session.delete(billing)
    db.session.commit()
    return jsonify({"success": True})
# --- Super Admin: Bots Management ---
from models.bot import Bot

@admin_api.route("/super/bots", methods=["GET"])
@super_admin_required
def list_bots():
    bots = Bot.query.all()
    return jsonify({"bots": [b.to_dict() for b in bots]})

@admin_api.route("/super/bots", methods=["POST"])
@super_admin_required
def create_bot():
    data = request.json
    bot = Bot(
        site_id=data["site_id"],
        name=data["name"],
        status=data.get("status", "active")
    )
    db.session.add(bot)
    db.session.commit()
    return jsonify({"success": True, "bot": bot.to_dict()})

@admin_api.route("/super/bots/<int:bot_id>", methods=["PUT"])
@super_admin_required
def update_bot(bot_id):
    data = request.json
    bot = Bot.query.get(bot_id)
    if not bot:
        return jsonify({"error": "Bot not found"}), 404
    if "name" in data:
        bot.name = data["name"]
    if "status" in data:
        bot.status = data["status"]
    db.session.commit()
    return jsonify({"success": True, "bot": bot.to_dict()})

@admin_api.route("/super/bots/<int:bot_id>", methods=["DELETE"])
@super_admin_required
def delete_bot(bot_id):
    bot = Bot.query.get(bot_id)
    if not bot:
        return jsonify({"error": "Bot not found"}), 404
    db.session.delete(bot)
    db.session.commit()
    return jsonify({"success": True})

@admin_api.route("/super/bots/<int:bot_id>/suspend", methods=["PUT"])
@super_admin_required
def suspend_bot(bot_id):
    bot = Bot.query.get(bot_id)
    if not bot:
        return jsonify({"error": "Bot not found"}), 404
    bot.status = "suspended"
    db.session.commit()
    return jsonify({"success": True, "bot": bot.to_dict()})
# --- Super Admin: Update Site Details ---
@admin_api.route("/super/sites/<int:site_id>/update", methods=["PUT"])
@super_admin_required
def update_site_full(site_id):
    data = request.json
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    # Update core details
    if 'name' in data:
        site.name = data['name'].strip()
    if 'domain' in data:
        site.domain = data['domain'].strip()
    if 'plan_id' in data:
        site.plan_id = int(data['plan_id'])
    if 'status' in data:
        site.status = data['status']
    db.session.commit()
    # Audit log: record who changed what
    admin_id = session.get("admin_id")
    log_action(admin_id, site.id, f"Site updated: {data}")
    return jsonify({"success": True, "site": site.to_dict()})

# --- Super Admin: Global Conversation Feed ---
@admin_api.route("/super/all-conversations", methods=["GET"])
@super_admin_required
def list_all_global_conversations():
    # Allows Platform Owner to see ALL traffic for quality/abuse monitoring
    logs = ChatLog.query.order_by(ChatLog.created_at.desc()).limit(100).all()
    return jsonify({"conversations": [l.to_dict() for l in logs]})

# --- Super Admin: System Health Check ---
@admin_api.route("/super/health-check", methods=["GET"])
@super_admin_required
def system_health():
    import os
    db_path = os.path.join(os.getcwd(), 'chatbot', 'instance', 'chatbot.db')
    return jsonify({
        "database": {
            "exists": os.path.exists(db_path),
            "writable": os.access(db_path, os.W_OK) if os.path.exists(db_path) else False
        },
        "system": "Operational",
        "api_status": "Healthy"
    })
# ---------------------------------------------------
# CLIENT ADMIN ROUTES
# ---------------------------------------------------
@admin_api.route("/client/stats", methods=["GET"])
def client_stats():
    site_id = session.get("site_id")
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    return jsonify({
        "status": site.status,
        "plan_name": site.plan.name if site.plan else "Free"
    })

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
    # Return a default structure if missing
    default_branding = {
        "bot_name": "Apollo Assistant",
        "initial_message": "Hello! How can I help you?",
        "primary_color": "#6366f1",
        "theme_mode": "light",
        "position": "bottom-right"
    }
    return jsonify({"branding": default_branding})

# ---------------------------------------------------
# CLIENT CONVERSATIONS (Chat History)
# ---------------------------------------------------
@admin_api.route("/client/conversations", methods=["GET"])
def client_conversations():
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    logs = ChatLog.query.filter_by(site_id=site_id).order_by(ChatLog.created_at.desc()).limit(50).all()
    return jsonify({"conversations": [l.to_dict() for l in logs]})

# ---------------------------------------------------
# CLIENT ANALYTICS / INSIGHTS
# ---------------------------------------------------
@admin_api.route("/client/analytics", methods=["GET"])
def client_analytics():
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    total = ChatLog.query.filter_by(site_id=site_id).count()
    success = ChatLog.query.filter_by(site_id=site_id).filter(ChatLog.confidence >= 0.8).count()
    return jsonify({
        "total_messages": total,
        "success_rate": round((success/total)*100, 1) if total > 0 else 0
    })

# ---------------------------------------------------
# CLIENT LEADS (Lead Capture)
# ---------------------------------------------------
@admin_api.route("/client/leads", methods=["GET"])
def client_leads():
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    # You may want to adjust the intent name for leads as needed
    leads = ChatLog.query.filter_by(site_id=site_id, detected_intent='CLIENT_INQUIRY').all()
    return jsonify({"leads": [l.to_dict() for l in leads]})
# ---------------------------------------------------
# CLIENT CONFIG ROUTE (Business Rules)
# ---------------------------------------------------
@admin_api.route("/client/config", methods=["GET", "POST"])
def client_config():
    # Priority: URL site_id (for Super Admin) then session site_id (for Client)
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400

    if request.method == "POST":
        data = request.json or {}
        for key, value in data.items():
            config = ClientConfig.query.filter_by(site_id=site_id, key=key).first()
            if not config:
                config = ClientConfig(site_id=site_id, key=key)
                db.session.add(config)
            config.value = value
        db.session.commit()
        return jsonify({"success": True})

    # GET logic: Auto-detect required keys from active intents
    configs = ClientConfig.query.filter_by(site_id=site_id).all()
    config_dict = {c.key: c.value for c in configs}

    from models import Intent
    active_intents = Intent.query.filter_by(site_id=site_id).all()
    # Extract all unique keys from blueprints like 'consultation_price', 'open_time'
    required_keys = set()
    for intent in active_intents:
        if intent.config_required:
            for k in intent.config_required:
                required_keys.add(k)

    # Return only the keys found in the current blueprints
    filtered_config = {k: config_dict.get(k, '') for k in required_keys}
    return jsonify({"config": filtered_config})

@admin_api.route("/client/intents", methods=["GET", "POST"])
def client_intents():
    site_id = request.args.get("site_id") or session.get("site_id")
    if not site_id:
        return jsonify({"error": "No site_id provided"}), 400
    
    if request.method == "POST":
        data = request.json
        new_intent = Intent(
            site_id=site_id,
            intent_name=data.get("intent_name"),
            response=data.get("response"),
            intent_type="info",
            confidence_threshold=0.7
        )
        db.session.add(new_intent)
        db.session.flush() # Flushes to generate the intent ID
        
        # --- NEW: Save the trigger phrases ---
        phrases = data.get("phrases", [])
        for p in phrases:
            if p:
                db.session.add(IntentPhrase(intent_id=new_intent.id, phrase=p))
        
        db.session.commit()
        return jsonify({"success": True})
        
    intents = Intent.query.filter_by(site_id=site_id).all()
    def intent_to_dict_full(i):
        d = i.to_dict() if hasattr(i, 'to_dict') else {}
        # Always include these fields
        d['intent_type'] = getattr(i, 'intent_type', None)
        d['config_required'] = getattr(i, 'config_required', [])
        d['workflow'] = getattr(i, 'workflow', None)
        d['confidence_threshold'] = getattr(i, 'confidence_threshold', None)
        return d
    return jsonify({"intents": [intent_to_dict_full(i) for i in intents]})

@admin_api.route("/client/intents/<int:intent_id>", methods=["PUT", "DELETE"])
def manage_client_intent(intent_id):
        # FIX: Prioritize site_id from URL query params (for Super Admin)
        site_id = request.args.get("site_id") or session.get("site_id")

        if not site_id:
            return jsonify({"error": "No site_id provided"}), 400

        intent = Intent.query.filter_by(id=intent_id, site_id=site_id).first()
        if not intent:
            return jsonify({"error": "Not found"}), 404

        if request.method == "DELETE":
            # Delete related workflows and phrases first to avoid integrity errors
            from models import Workflow, IntentPhrase
            Workflow.query.filter_by(intent_id=intent.id).delete()
            IntentPhrase.query.filter_by(intent_id=intent.id).delete()
            db.session.delete(intent)
            db.session.commit()
            return jsonify({"success": True})

        if request.method == "PUT":
            data = request.json
            intent.intent_name = data.get("intent_name", intent.intent_name)
            intent.response = data.get("response", intent.response)

            # --- NEW: Update phrases ---
            phrases = data.get("phrases")
            if phrases is not None:
                # Delete old phrases and attach the new ones
                IntentPhrase.query.filter_by(intent_id=intent.id).delete()
                for p in phrases:
                    if p:
                        db.session.add(IntentPhrase(intent_id=intent.id, phrase=p))

            db.session.commit()
            return jsonify({"success": True})
# ---------------------------------------------------
# BASIC HEALTH CHECK
# ---------------------------------------------------
@admin_api.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "message": "Admin API is reachable"})




# --- AUDIT LOGS ---
@admin_api.route("/super/audit-logs", methods=["GET"])
@super_admin_required
def load_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return jsonify({"logs": [{"timestamp": l.timestamp, "action": l.action, "admin_id": l.admin_id} for l in logs]})




# ---------------------------------------------------
# SITE MANAGEMENT
# ---------------------------------------------------
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
        owner_email = data.get("owner_email", "").strip()
        admin_username = data.get("admin_username", "").strip()
        admin_password = data.get("admin_password", "").strip()

        if not name:
            return jsonify({"error": "Site name is required"}), 400

        if not admin_username or not admin_password:
            return jsonify({"error": "Admin username & password required"}), 400

        # Check duplicate username
        if Admin.query.filter_by(username=admin_username).first():
            return jsonify({"error": "Admin username already exists"}), 400

        # Create Site
        new_site = Site(
            name=name,
            domain=domain,
            owner_email=owner_email,
            status="active",
            bot_name=f"{name} Bot"
        )

        db.session.add(new_site)
        db.session.flush()  # important to get site.id

        # Create Client Admin
        new_admin = Admin(
            username=admin_username,
            site_id=new_site.id,
            is_super=False
        )
        new_admin.set_password(admin_password)

        db.session.add(new_admin)
        db.session.commit()

        return jsonify({
            "success": True,
            "site": new_site.to_dict(),
            "admin_username": admin_username
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# PLAN MANAGEMENT
# ---------------------------------------------------
@admin_api.route("/super/plans", methods=["GET"])
@super_admin_required
def list_plans():
    plans = Plan.query.all()
    return jsonify({"plans": [p.to_dict() for p in plans]})


@admin_api.route("/super/plans", methods=["POST"])
@super_admin_required
def create_plan():
    data = request.json or {}

    try:
        plan = Plan(
            name=data.get("name"),
            price=float(data.get("price", 0)),
            max_monthly_chats=int(data.get("max_monthly_chats", 0))
        )

        db.session.add(plan)
        db.session.commit()

        return jsonify({
            "success": True,
            "plan": plan.to_dict()
        })

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Plan already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# TEMPLATE FILE LIST
# ---------------------------------------------------
@admin_api.route("/super/template_files", methods=["GET"])
@super_admin_required
def list_template_files():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, "intent_templates")

        if not os.path.exists(template_dir):
            return jsonify({"files": []})

        files = [
            f for f in os.listdir(template_dir)
            if f.endswith(".json")
        ]

        return jsonify({"files": files})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------
# IMPORT TEMPLATE
# ---------------------------------------------------

@admin_api.route("/super/import_template", methods=["POST"])
@super_admin_required
def import_template():
    data = request.get_json()
    filename = data.get("filename")
    site_id = data.get("site_id")
    if not filename or not site_id:
        return jsonify({"error": "Missing filename or site_id"}), 400

    import os
    import json
    from models import Intent, IntentPhrase
    from database import db
    template_path = os.path.join(os.path.dirname(__file__), "..", "intent_templates", filename)
    template_path = os.path.abspath(template_path)
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

# ---------------------------------------------------
# ADMIN UPDATE ROUTE
# ---------------------------------------------------

# ---------------------------------------------------
# IMPERSONATION ROUTE
# ---------------------------------------------------


# --- MISSING ADMIN MANAGEMENT ROUTES ---

@admin_api.route("/super/admins", methods=["GET"])
@super_admin_required
def list_admins():
    admins = Admin.query.all()
    return jsonify({
        "admins": [{
            "id": a.id,
            "username": a.username,
            "site_id": a.site_id,
            "is_super": a.is_super,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in admins]
    })

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


@admin_api.route("/super/sites/<int:site_id>/status", methods=["PUT"])
@super_admin_required
def toggle_site_status(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "Site not found"}), 404
    # Toggle status between active and suspended
    site.status = 'suspended' if site.status == 'active' else 'active'
    db.session.commit()
    return jsonify({"success": True, "new_status": site.status})

@admin_api.route("/super/sites/<int:site_id>/impersonate", methods=["POST"])
@super_admin_required
def impersonate_site(site_id):
    # Find any admin associated with this site
    target_admin = Admin.query.filter_by(site_id=site_id, is_super=False).first()
    if not target_admin:
        return jsonify({"error": "No client admin found for this site"}), 404
    # Set session to act as this client admin
    session["admin_id"] = target_admin.id
    session["site_id"] = site_id
    return jsonify({
        "success": True,
        "redirect": "/admin/dashboard"
    })
