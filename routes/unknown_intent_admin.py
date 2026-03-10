"""
Admin API routes for fallback optimization and unknown intent mapping.
"""
from flask import Blueprint, request, jsonify, render_template, session
from functools import wraps

from database import db
from models import Admin, UnknownIntentLog, Intent, IntentConfidenceWeight
from services.fallback_optimizer import get_optimizer

unknown_intent_bp = Blueprint('unknown_intents', __name__)


def admin_required(f):
    """Decorator to require admin authentication via session or X-Admin-ID header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check session first (primary auth method)
        admin_id = session.get('admin_id')
        
        # Fallback to X-Admin-ID header if session not available
        if not admin_id:
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
        "id": 123,
        "message": "user said this",
        "fallback_type": "llm",
        "count": 5,
        "first_seen": "2026-03-09T10:00:00",
        "last_seen": "2026-03-09T15:30:00",
        "llm_response_sample": "I'm not sure what you mean...",
        "similarity_suggestions": [
            {"intent_id": 5, "intent_name": "billing_inquiry", "match_score": 0.87}
        ]
    }
    """
    site_id = request.admin.site_id
    limit = request.args.get('limit', 20, type=int)
    
    optimizer = get_optimizer()
    unknowns = optimizer.get_unmapped_unknowns(site_id, limit)
    
    # Enhance with semantic similarity suggestions
    from models import Intent
    from services.embedding_cache import get_embedding_cache
    from sentence_transformers import util as st_util
    import numpy as np
    
    cache = get_embedding_cache()
    model = None
    
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except:
        model = None  # Embeddings not available
    
    enhanced = []
    for unknown in unknowns:
        item = {
            'id': unknown['sample_log_id'],
            'message': unknown['message'],
            'count': unknown['count'],
            'similarity_suggestions': []
        }
        
        # Add semantic intent suggestions if embeddings available
        if model:
            try:
                # Get message embedding (check cache first)
                cache_key = f"msg_{unknown['message']}"
                msg_cached = cache.get(cache_key)
                if msg_cached is not None:
                    msg_emb = np.array(msg_cached)
                else:
                    msg_emb = model.encode(unknown['message'], convert_to_tensor=False)
                    cache.set(cache_key, msg_emb)
                
                # Get all intents for this site
                intents = Intent.query.filter_by(site_id=site_id).all()
                
                scores = []
                for intent in intents:
                    # Get intent embedding from first phrase or compute from name
                    if intent.phrases:
                        phrase_text = intent.phrases[0].phrase
                        cache_key = f"phrase_{phrase_text}"
                        cached = cache.get(cache_key)
                        if cached is not None:
                            intent_emb = np.array(cached)
                        else:
                            intent_emb = model.encode(phrase_text, convert_to_tensor=False)
                            cache.set(cache_key, intent_emb)
                    else:
                        # Use intent name as fallback
                        intent_emb = model.encode(intent.intent_name, convert_to_tensor=False)
                    
                    # Calculate similarity
                    from sklearn.metrics.pairwise import cosine_similarity
                    sim = cosine_similarity([msg_emb], [intent_emb])[0][0]
                    
                    if sim > 0.5:  # Only suggest if decent match
                        scores.append({
                            'intent_id': intent.id,
                            'intent_name': intent.intent_name,
                            'match_score': float(round(sim, 3))
                        })
                
                # Sort by score and take top 3
                item['similarity_suggestions'] = sorted(scores, key=lambda x: x['match_score'], reverse=True)[:3]
            except Exception as e:
                pass  # Silently skip if similarity computation fails
        
        # Get full detail from DB
        log = UnknownIntentLog.query.get(item['id'])
        if log:
            item['first_seen'] = log.created_at.isoformat() if log.created_at else None
            item['fallback_type'] = log.fallback_type
            item['llm_response_sample'] = (log.llm_response[:80] + '...') if log.llm_response else None
        
        enhanced.append(item)
    
    return jsonify({
        'success': True,
        'count': len(enhanced),
        'unknowns': enhanced
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
    Get full details and audit trail of a specific unknown intent log.
    
    Returns:
    {
        "id": 123,
        "message": "user message",
        "fallback_type": "llm",
        "llm_response": "...",
        "created_at": "2026-03-09T10:00:00",
        "resolved": false,
        "mapped_intent_id": null,
        "mapped_by": null,
        "mapped_at": null,
        "phrase_auto_trained": false,
        "similarity_suggestions": [...]
    }
    """
    log = UnknownIntentLog.query.get(log_id)
    
    if not log or log.site_id != request.admin.site_id:
        return jsonify({'error': 'Log not found'}), 404
    
    # Generate similarity suggestions for this specific message
    suggestions = []
    try:
        from models import Intent
        from sentence_transformers import SentenceTransformer, util as st_util
        from services.embedding_cache import get_embedding_cache
        import numpy as np
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        cache = get_embedding_cache()
        
        # Get message embedding
        cache_key = f"msg_{log.message}"
        msg_cached = cache.get(cache_key)
        if msg_cached is not None:
            msg_emb = np.array(msg_cached)
        else:
            msg_emb = model.encode(log.message, convert_to_tensor=False)
            cache.set(cache_key, msg_emb)
        
        # Get intents and compute similarity
        intents = Intent.query.filter_by(site_id=request.admin.site_id).all()
        for intent in intents:
            if intent.phrases:
                phrase_text = intent.phrases[0].phrase
                cache_key = f"phrase_{phrase_text}"
                cached = cache.get(cache_key)
                if cached is not None:
                    intent_emb = np.array(cached)
                else:
                    intent_emb = model.encode(phrase_text, convert_to_tensor=False)
                    cache.set(cache_key, intent_emb)
            else:
                intent_emb = model.encode(intent.intent_name, convert_to_tensor=False)
            
            from sklearn.metrics.pairwise import cosine_similarity
            sim = cosine_similarity([msg_emb], [intent_emb])[0][0]
            
            if sim > 0.5:
                suggestions.append({
                    'intent_id': intent.id,
                    'intent_name': intent.intent_name,
                    'match_score': float(round(sim, 3))
                })
        
        suggestions = sorted(suggestions, key=lambda x: x['match_score'], reverse=True)[:5]
    except Exception as e:
        pass  # Silently skip if embeddings not available
    
    return jsonify({
        'success': True,
        'log': {
            **log.to_dict(include_admin_fields=True),
            'similarity_suggestions': suggestions
        }
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


# ===== UI ROUTES (non-API) =====

@unknown_intent_bp.route('/manager', methods=['GET'])
@admin_required
def unknown_intent_manager():
    """
    Serve the Unknown Intent Manager UI page.
    Allows admins to review, map, and auto-train unknown intents.
    """
    return render_template('unknown_intent_manager.html')


# ===== ADDITIONAL ENDPOINTS =====

@unknown_intent_bp.route('/intents', methods=['GET'])
@admin_required
def get_intents_for_mapping():
    """
    Get list of available intents for mapping.
    Used by the mapping UI for intent selection.
    
    Returns:
    {
        "success": true,
        "intents": [
            {
                "id": 1,
                "intent_name": "billing_inquiry",
                "phrases": ["how much", "pricing", ...]
            },
            ...
        ]
    }
    """
    site_id = request.admin.site_id
    
    intents = Intent.query.filter_by(site_id=site_id).all()
    
    result = [
        {
            'id': i.id,
            'intent_name': i.intent_name,
            'phrases': [p.phrase for p in i.phrases.all()[:5]],  # First 5 phrases
            'phrase_count': i.phrases.count()
        }
        for i in intents
    ]
    
    return jsonify({
        'success': True,
        'intents': result
    })
