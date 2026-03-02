from flask import Blueprint, jsonify, request, session
from models.site import Site
from models.admin import Admin
from models.platform_settings import AuditLog
from models.billing import Billing
from models.bot import Bot
from models.chat_log import ChatLog
from models.plan import Plan
from database import db
import os
from functools import wraps

# Updated @super_admin_required decorator to use consistent session key
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

super_admin_api = Blueprint('super_admin_api', __name__, url_prefix='/api/super')

@super_admin_api.route('/stats', methods=['GET'])
def super_stats():
    site_count = Site.query.count()
    total_chats = ChatLog.query.count()
    return jsonify({"site_count": site_count, "total_chats": total_chats})

@super_admin_api.route('/settings', methods=['GET'])
def list_super_settings():
    return jsonify({"settings": [
        {"key": "OPENAI_API_KEY", "value": "********"},
        {"key": "CRM_WEBHOOK_URL", "value": "Active"}
    ]})

# Add other super admin routes here

# Add routes for Super Admin features

@super_admin_api.route('/dashboard-data', methods=['GET'])
@super_admin_required
def get_dashboard_data():
    stats = {
        "total_clients": Site.query.count(),
        "active_plans": Plan.query.filter_by(is_active=True).count(),
        "total_conversations": ChatLog.query.count()
    }
    return jsonify(stats)

@super_admin_api.route('/clients', methods=['GET'])
@super_admin_required
def get_clients():
    clients = Site.query.all()
    client_list = [{"id": client.id, "name": client.name, "status": client.status} for client in clients]
    return jsonify(client_list)

@super_admin_api.route('/plans', methods=['GET'])
@super_admin_required
def get_plans():
    plans = Plan.query.all()
    plan_list = [{"id": plan.id, "name": plan.name, "is_active": plan.is_active} for plan in plans]
    return jsonify(plan_list)

@super_admin_api.route('/audit-logs', methods=['GET'])
@super_admin_required
def get_audit_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    log_list = [{"id": log.id, "action": log.action, "timestamp": log.timestamp} for log in logs]
    return jsonify(log_list)