from collections import defaultdict
from datetime import datetime
from database import db
from config import CONFIDENCE_THRESHOLD, FALLBACK_MESSAGES
from core.tokenizer import tokenize, STOP_WORDS
from core.synonyms import canonical
from models.intent import Intent, IntentPhrase
from models import UnansweredQuestion
from sqlalchemy import or_
from thefuzz import fuzz
import random
import requests
from config import CRM_WEBHOOK_URL, CRM_WEBHOOK_KEY, HANDOFF_KEYWORDS

# Higher threshold for direct matches, lower for "I think you mean..."
HIGH_CONFIDENCE = 0.85

# Optional sentence-transformers support
USE_EMBEDDINGS = False
MODEL = None
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    USE_EMBEDDINGS = True
except Exception:
    USE_EMBEDDINGS = False


def detect_intent(message: str, site_id: int) -> dict:
    """
    Detect intent for a given site_id and message.
    Uses fuzzy set matching to handle partial queries (e.g., 'price' matches 'what is price').
    """
    # 1. Input Validation
    if not message:
        return _fallback_response()
    
    # Clean input
    message_cleaned = message.lower().strip()

    # 2. Load Intents (Site Specific + Global)
    try:
        # Convert site_id to int safely
        site_id_int = int(site_id)
        intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id_int)).all()
    except Exception as e:
        print(f"Error loading intents: {e}")
        return _fallback_response()

    if not intents:
        return _fallback_response()

    best = {
        'intent': None,
        'score': 0.0
    }

    # 3. Matching Logic
    for intent in intents:
        # Check all phrases for this intent
        for phrase_obj in intent.phrases:
            phrase = (phrase_obj.phrase or '').lower().strip()
            if not phrase:
                continue

            # --- ALGORITHM EXPLANATION ---
            # token_set_ratio: Great for ignoring extra words. 
            # Ex: User="price", Phrase="what is the price" -> Score 100
            # Ex: User="timings", Phrase="hospital timings" -> Score 100
            score_set = fuzz.token_set_ratio(message_cleaned, phrase)
            
            # token_sort_ratio: Great for wrong order.
            # Ex: User="open when", Phrase="when open" -> Score 100
            score_sort = fuzz.token_sort_ratio(message_cleaned, phrase)
            
            # Weighted Score: Prioritize the Set ratio as it handles keywords best
            final_score = max(score_set, score_sort) / 100.0

            if final_score > best['score']:
                best['score'] = final_score
                best['intent'] = intent

    # 4. Process Best Match
    if best['intent']:
        # Use configured threshold for the intent, or global default
        threshold = getattr(best['intent'], 'confidence_threshold', CONFIDENCE_THRESHOLD) or CONFIDENCE_THRESHOLD
        
        # Scale score (cap at 1.0)
        confidence = min(1.0, best['score'])
        
        print(f"DEBUG: Msg='{message}' | Match='{best['intent'].intent_name}' | Score={confidence}")

        # A. High Confidence Match
        if confidence >= threshold:
            return _success_response(best['intent'], confidence, site_id, message)
        
        # B. Medium Confidence (Suggestion)
        elif confidence >= (threshold - 0.15):
             return {
                'intent_name': best['intent'].intent_name,
                'intent_type': best['intent'].intent_type,
                'response': f"I'm not 100% sure, but I think you're asking about {best['intent'].intent_name}. Is that correct?",
                'confidence': confidence,
                'handoff': None
            }

    # 5. No Match Found
    _log_unanswered(message)
    return _fallback_response()


def _success_response(intent, confidence, site_id, user_message):
    """Helper to build success response and trigger hooks if needed"""
    intent_type = (intent.intent_type or 'info').upper()
    
    # Handle HUMAN handoff webhook
    if intent_type == 'HUMAN':
        try:
            payload = {'intent': intent.intent_name, 'message': user_message, 'site_id': site_id}
            headers = {'X-Webhook-Key': CRM_WEBHOOK_KEY}
            requests.post(CRM_WEBHOOK_URL, json=payload, headers=headers, timeout=2)
        except Exception:
            pass # Fail silently for webhook

    return {
        'intent_name': intent.intent_name,
        'intent_type': intent.intent_type,
        'response': intent.response,
        'handoff': intent.intent_type if intent_type in ('LEAD', 'HUMAN') else None,
        'confidence': confidence
    }

def _fallback_response():
    return {
        'intent_name': 'UNKNOWN',
        'intent_type': 'UNKNOWN',
        'response': random.choice(FALLBACK_MESSAGES),
        'confidence': 0.0
    }

def _log_unanswered(message):
    try:
        q = UnansweredQuestion.query.filter_by(question=message).first()
        if q:
            q.times_asked = (q.times_asked or 1) + 1
            q.last_asked = datetime.utcnow()
        else:
            q = UnansweredQuestion(question=message)
            db.session.add(q)
        db.session.commit()
    except Exception:
        db.session.rollback()