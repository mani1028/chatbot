from flask import Blueprint, jsonify, request, session
from models.site import Site
from models.admin import Admin
from models.platform_settings import AuditLog
from models.billing import Billing
from models.bot import Bot
from models.chat_log import ChatLog
from models.plan import Plan
from models.phase1_metrics import Phase1Metrics
from models.unknown_intent_log import UnknownIntentLog
from database import db
from sqlalchemy import func
from datetime import datetime, timedelta
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

super_admin_api = Blueprint('super_admin_api', __name__)

@super_admin_api.route('/stats', methods=['GET'])
def super_stats():
    site_count = Site.query.count()
    total_chats = ChatLog.query.count()
    return jsonify({"site_count": site_count, "total_chats": total_chats})

@super_admin_api.route('/sites', methods=['GET'])
@super_admin_required
def list_sites():
    """List all sites for super admin"""
    sites = Site.query.all()
    sites_list = [s.to_dict() for s in sites]
    return jsonify({"sites": sites_list})

@super_admin_api.route('/plans', methods=['GET'])
@super_admin_required
def list_plans():
    """List all plans for super admin"""
    plans = Plan.query.all()
    plans_list = [{"id": p.id, "name": p.name, "is_active": p.is_active} for p in plans]
    return jsonify(plans_list)

@super_admin_api.route('/analytics', methods=['GET'])
@super_admin_required
def get_analytics():
    """Get platform analytics"""
    stats = {
        "total_clients": Site.query.count(),
        "active_plans": Plan.query.filter_by(is_active=True).count(),
        "total_conversations": ChatLog.query.count()
    }
    return jsonify(stats)

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

@super_admin_api.route('/learning-metrics', methods=['GET'])
@super_admin_required
def learning_metrics():
    """
    Get learning analytics metrics for the platform.
    
    Query Params:
    - range: 24h | 7d | 30d (default: 7d)
    - site_id: optional (if omitted -> global aggregate)
    
    Returns JSON with:
    - total_messages, unknown_count, unknown_rate
    - llm_calls, llm_rate
    - confidence_distribution (LOW, MID, HIGH)
    - unknown_logged, unknown_mapped, mapping_conversion_rate
    - estimated_llm_cost, estimated_cost_saved
    """
    
    # --- 1. Parse Params ---
    range_param = request.args.get('range', '7d')
    site_id = request.args.get('site_id', type=int)
    
    now = datetime.utcnow()
    
    if range_param == '24h':
        start_date = now - timedelta(hours=24)
    elif range_param == '30d':
        start_date = now - timedelta(days=30)
    else:  # Default 7d
        start_date = now - timedelta(days=7)
    
    # --- 2. Base Queries ---
    metrics_query = db.session.query(Phase1Metrics).filter(
        Phase1Metrics.timestamp >= start_date
    )
    
    unknown_query = db.session.query(UnknownIntentLog).filter(
        UnknownIntentLog.created_at >= start_date
    )
    
    if site_id:
        metrics_query = metrics_query.filter(Phase1Metrics.site_id == site_id)
        unknown_query = unknown_query.filter(UnknownIntentLog.site_id == site_id)
    
    # --- 3. Core Aggregates ---
    total_messages = metrics_query.count()
    
    unknown_count = metrics_query.filter(
        Phase1Metrics.intent_name == 'UNKNOWN'
    ).count()
    
    llm_calls = metrics_query.filter(
        Phase1Metrics.llm_called == True
    ).count()
    
    # Confidence distribution
    confidence_query = db.session.query(
        Phase1Metrics.confidence_band,
        func.count(Phase1Metrics.id)
    ).filter(
        Phase1Metrics.timestamp >= start_date
    )
    
    if site_id:
        confidence_query = confidence_query.filter(
            Phase1Metrics.site_id == site_id
        )
    
    confidence_counts = dict(confidence_query.group_by(
        Phase1Metrics.confidence_band
    ).all())
    
    # Normalize confidence bands
    confidence_distribution = {
        "LOW": confidence_counts.get("LOW", 0),
        "MID": confidence_counts.get("MID", 0),
        "HIGH": confidence_counts.get("HIGH", 0)
    }
    
    # --- 4. Unknown Funnel ---
    total_unknown_logged = unknown_query.count()
    
    unknown_mapped = unknown_query.filter(
        UnknownIntentLog.resolved == True
    ).count()
    
    # --- 5. Derived Metrics ---
    unknown_rate = round(unknown_count / total_messages, 4) if total_messages else 0
    llm_rate = round(llm_calls / total_messages, 4) if total_messages else 0
    
    mapping_conversion_rate = (
        round(unknown_mapped / total_unknown_logged, 4)
        if total_unknown_logged else 0
    )
    
    # --- 6. Estimated Cost ---
    # Assume avg LLM cost per call ($0.0006)
    AVG_LLM_COST = 0.0006
    estimated_cost = round(llm_calls * AVG_LLM_COST, 4)
    
    # Estimate savings from mapped unknowns
    estimated_cost_saved = round(unknown_mapped * AVG_LLM_COST, 4)
    
    # --- 7. Response ---
    return jsonify({
        "range": range_param,
        "site_id": site_id,
        "total_messages": total_messages,
        "unknown_count": unknown_count,
        "unknown_rate": unknown_rate,
        "llm_calls": llm_calls,
        "llm_rate": llm_rate,
        "confidence_distribution": confidence_distribution,
        "unknown_logged": total_unknown_logged,
        "unknown_mapped": unknown_mapped,
        "mapping_conversion_rate": mapping_conversion_rate,
        "estimated_llm_cost": estimated_cost,
        "estimated_cost_saved": estimated_cost_saved
    })

@super_admin_api.route('/learning-metrics-trend', methods=['GET'])
@super_admin_required
def learning_metrics_trend():
    """Get daily LLM rate trend for past 7 days."""
    site_id = request.args.get('site_id', type=int)
    now = datetime.utcnow()
    start_date = now - timedelta(days=7)
    
    # Query metrics grouped by day
    daily_query = db.session.query(
        func.date(Phase1Metrics.timestamp).label('date'),
        func.count(Phase1Metrics.id).label('total'),
        func.sum(func.cast(Phase1Metrics.llm_called, db.Integer)).label('llm_count')
    ).filter(
        Phase1Metrics.timestamp >= start_date
    )
    
    if site_id:
        daily_query = daily_query.filter(Phase1Metrics.site_id == site_id)
    
    daily_data = daily_query.group_by(func.date(Phase1Metrics.timestamp)).all()
    
    # Format response (7 days, fill missing days with 0)
    trend = []
    for i in range(7):
        day = (start_date + timedelta(days=i)).date()
        day_str = day.strftime('%Y-%m-%d')
        
        day_data = next((d for d in daily_data if d[0] == day), None)
        if day_data:
            total, llm_count = day_data[1], day_data[2] or 0
            llm_rate = round((llm_count / total * 100), 2) if total else 0
        else:
            total = 0
            llm_count = 0
            llm_rate = 0
        
        trend.append({
            "date": day_str,
            "total": total,
            "llm_calls": llm_count,
            "llm_rate": llm_rate
        })
    
    return jsonify({"trend": trend, "site_id": site_id})

@super_admin_api.route('/tenant-comparison', methods=['GET'])
@super_admin_required
def tenant_comparison():
    """Get metrics for all tenants for comparison."""
    now = datetime.utcnow()
    range_param = request.args.get('range', '7d')
    
    if range_param == '24h':
        start_date = now - timedelta(hours=24)
    elif range_param == '30d':
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=7)
    
    # Get all sites
    sites = Site.query.all()
    tenant_data = []
    
    for site in sites:
        # Count metrics for this site
        total_msgs = Phase1Metrics.query.filter(
            Phase1Metrics.site_id == site.id,
            Phase1Metrics.timestamp >= start_date
        ).count()
        
        unknown_msgs = Phase1Metrics.query.filter(
            Phase1Metrics.site_id == site.id,
            Phase1Metrics.timestamp >= start_date,
            Phase1Metrics.intent_name == 'UNKNOWN'
        ).count()
        
        llm_calls = Phase1Metrics.query.filter(
            Phase1Metrics.site_id == site.id,
            Phase1Metrics.timestamp >= start_date,
            Phase1Metrics.llm_called == True
        ).count()
        
        unknown_logged = UnknownIntentLog.query.filter(
            UnknownIntentLog.site_id == site.id,
            UnknownIntentLog.created_at >= start_date
        ).count()
        
        unknown_mapped = UnknownIntentLog.query.filter(
            UnknownIntentLog.site_id == site.id,
            UnknownIntentLog.created_at >= start_date,
            UnknownIntentLog.resolved == True
        ).count()
        
        # Calculate rates
        unknown_rate = round((unknown_msgs / total_msgs * 100), 2) if total_msgs else 0
        llm_rate = round((llm_calls / total_msgs * 100), 2) if total_msgs else 0
        mapping_conv = round((unknown_mapped / unknown_logged * 100), 2) if unknown_logged else 0
        
        tenant_data.append({
            "id": site.id,
            "name": site.name,
            "total_messages": total_msgs,
            "llm_rate": llm_rate,
            "unknown_rate": unknown_rate,
            "mapping_conversion": mapping_conv,
            "unknown_mapped": unknown_mapped,
            "status": site.status
        })
    
    # Sort by LLM rate descending
    tenant_data.sort(key=lambda x: x['llm_rate'], reverse=True)
    
    return jsonify({"tenants": tenant_data, "range": range_param})

@super_admin_api.route('/auto-suggestion-metrics', methods=['GET'])
@super_admin_required
def auto_suggestion_metrics():
    """Get metrics on phrases that could be auto-suggested/mapped."""
    site_id = request.args.get('site_id', type=int)
    now = datetime.utcnow()
    start_date = now - timedelta(days=7)
    
    # Get unknown intents that have similar phrases
    unknown_logs = UnknownIntentLog.query.filter(
        UnknownIntentLog.created_at >= start_date
    )
    
    if site_id:
        unknown_logs = unknown_logs.filter(UnknownIntentLog.site_id == site_id)
    
    unknown_logs = unknown_logs.all()
    
    # Count phrases that appear multiple times (suggesting they could be grouped)
    phrase_counts = {}
    for log in unknown_logs:
        phrase = (log.message or '').lower().strip()
        if phrase:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    
    # Find high-frequency phrases (appear 2+ times)
    high_frequency = [
        {"phrase": p, "count": c, "potential_savings": round(c * 0.0006, 4)}
        for p, c in phrase_counts.items() if c >= 2
    ]
    
    high_frequency.sort(key=lambda x: x['count'], reverse=True)
    
    # Calculate learning efficiency
    total_unknown = len(unknown_logs)
    auto_suggestible = len(high_frequency)
    learning_efficiency = round((auto_suggestible / total_unknown * 100), 2) if total_unknown else 0
    
    return jsonify({
        "site_id": site_id,
        "total_unknown": total_unknown,
        "auto_suggestible_phrases": len(high_frequency),
        "learning_efficiency": learning_efficiency,
        "top_phrases": high_frequency[:10],
        "potential_daily_savings": round(sum(p['potential_savings'] for p in high_frequency), 4)
    })