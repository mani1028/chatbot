"""
Admin API routes for fallback optimization and unknown intent mapping.
"""
from flask import Blueprint, request, jsonify
from functools import wraps

from database import db
from models import Admin, UnknownIntentLog, Intent, IntentConfidenceWeight
from services.fallback_optimizer import get_optimizer

unknown_intent_bp = Blueprint('unknown_intents', __name__, url_prefix='/admin/api/unknown')


def admin_required(f):
    """Decorator to require admin authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = request.headers.get('X-Admin-ID')
        if not admin_id:
            return jsonify({'error': 'Admin authentication required'}), 401
        
        admin = Admin.query.get(admin_id)
        if not admin:
            return jsonify({'error': 'Invalid admin ID'}), 401
        
        # Store admin in context
        request.admin = admin
        return f(*args, **kwargs)
    return decorated_function


@unknown_intent_bp.route('/unmapped', methods=['GET'])
@admin_required
def get_unmapped_unknowns():
    """
    Get most common unmapped unknown messages for this admin's site.
    
    Returns list of:
    {
        "message": "user said this",
        "count": 5,
        "sample_log_id": 123
    }
    """
    site_id = request.admin.site_id
    limit = request.args.get('limit', 20, type=int)
    
    optimizer = get_optimizer()
    unknowns = optimizer.get_unmapped_unknowns(site_id, limit)
    
    return jsonify({
        'success': True,
        'count': len(unknowns),
        'unknowns': unknowns
    })


@unknown_intent_bp.route('/map', methods=['POST'])
@admin_required
def map_unknown_to_intent():
    """
    Admin maps an unknown message to an existing intent.
    
    Optionally auto-trains the phrase.
    
    Request body:
    {
        "unknown_log_id": 123,
        "intent_id": 456,
        "auto_train_phrases": true
    }
    """
    data = request.get_json() or {}
    
    unknown_log_id = data.get('unknown_log_id')
    intent_id = data.get('intent_id')
    auto_train = data.get('auto_train_phrases', True)
    
    if not unknown_log_id or not intent_id:
        return jsonify({'error': 'missing unknown_log_id or intent_id'}), 400
    
    site_id = request.admin.site_id
    admin_id = request.admin.id
    
    optimizer = get_optimizer()
    success, message = optimizer.map_unknown_to_intent(
        unknown_log_id,
        intent_id,
        site_id,
        admin_id,
        auto_train_phrases=auto_train
    )
    
    return jsonify({
        'success': success,
        'message': message
    }), (200 if success else 400)


@unknown_intent_bp.route('/stats', methods=['GET'])
@admin_required
def get_fallback_stats():
    """
    Get fallback statistics for this site.
    
    Returns:
    {
        "total_fallbacks": 150,
        "mapped_count": 130,
        "unmapped_count": 20,
        "coverage": 0.867,
        "by_type": {
            "llm": 100,
            "throttle": 30,
            "confidence": 20
        }
    }
    """
    site_id = request.admin.site_id
    optimizer = get_optimizer()
    stats = optimizer.get_fallback_stats(site_id)
    
    return jsonify({
        'success': True,
        'stats': stats
    })


@unknown_intent_bp.route('/intent-metrics', methods=['GET'])
@admin_required
def get_intent_metrics():
    """
    Get confidence weight metrics for all intents.
    
    Useful for understanding which intents are performing well.
    
    Returns:
    [
        {
            "intent_id": 1,
            "total_detections": 50,
            "success_rate": 0.92,
            "escalation_rate": 0.08,
            "confidence_multiplier": 1.1
        },
        ...
    ]
    """
    site_id = request.admin.site_id
    intent_id = request.args.get('intent_id', type=int)
    
    optimizer = get_optimizer()
    metrics = optimizer.get_intent_metrics(site_id, intent_id)
    
    return jsonify({
        'success': True,
        'metrics': metrics
    })


@unknown_intent_bp.route('/log/<int:log_id>', methods=['GET'])
@admin_required
def get_unknown_log(log_id):
    """
    Get details of a specific unknown intent log.
    """
    log = UnknownIntentLog.query.get(log_id)
    
    if not log or log.site_id != request.admin.site_id:
        return jsonify({'error': 'Log not found'}), 404
    
    return jsonify({
        'success': True,
        'log': log.to_dict()
    })


@unknown_intent_bp.route('/batch-map', methods=['POST'])
@admin_required
def batch_map_unknowns():
    """
    Admin maps multiple unknown messages to intents in one call.
    
    Request body:
    {
        "mappings": [
            {
                "unknown_log_id": 123,
                "intent_id": 456,
                "auto_train_phrases": true
            },
            ...
        ]
    }
    
    Returns list of results.
    """
    data = request.get_json() or {}
    mappings = data.get('mappings', [])
    
    if not mappings:
        return jsonify({'error': 'No mappings provided'}), 400
    
    site_id = request.admin.site_id
    admin_id = request.admin.id
    
    optimizer = get_optimizer()
    results = []
    
    for mapping in mappings:
        unknown_log_id = mapping.get('unknown_log_id')
        intent_id = mapping.get('intent_id')
        auto_train = mapping.get('auto_train_phrases', True)
        
        success, message = optimizer.map_unknown_to_intent(
            unknown_log_id,
            intent_id,
            site_id,
            admin_id,
            auto_train_phrases=auto_train
        )
        
        results.append({
            'unknown_log_id': unknown_log_id,
            'success': success,
            'message': message
        })
    
    return jsonify({
        'success': True,
        'results': results,
        'success_count': sum(1 for r in results if r['success']),
        'total': len(results)
    })
