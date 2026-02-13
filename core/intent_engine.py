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

FUZZY_TOKEN_THRESHOLD = 80
HIGH_CONFIDENCE = 0.85

# Forcefully disable heavy embeddings so the app doesn't freeze/hang on start
USE_EMBEDDINGS = False
MODEL = None

def detect_intent(message: str, site_id: int) -> dict:
    if not message or not str(site_id).isdigit() and not isinstance(site_id, int):
        return {'intent_name': 'UNKNOWN', 'intent_type': 'UNKNOWN', 'response': random.choice(FALLBACK_MESSAGES), 'confidence': 0.0}

    tokens = tokenize(message)
    if not tokens:
        return {'intent_name': 'UNKNOWN', 'intent_type': 'UNKNOWN', 'response': random.choice(FALLBACK_MESSAGES), 'confidence': 0.0}
    
    intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id)).all()

    best = {'intent': None, 'phrase': None, 'score': 0.0}

    for intent in intents:
        for phrase_obj in intent.phrases:
            phrase = phrase_obj.phrase or ''
            p_tokens = tokenize(phrase)
            if not p_tokens:
                continue

            token_weights = []
            for t in p_tokens:
                if t in STOP_WORDS: token_weights.append(0.2)
                elif len(t) <= 3: token_weights.append(0.6)
                else: token_weights.append(1.0)

            total_weight = sum(token_weights) or 1.0
            matched_weight = 0.0

            for idx, p_tok in enumerate(p_tokens):
                best_tok_score = 0.0
                p_can = canonical(p_tok)
                for u_tok in tokens:
                    u_can = canonical(u_tok)
                    if p_can == u_can:
                        best_tok_score = 1.0
                        break
                    score = fuzz.ratio(p_tok, u_tok) / 100.0
                    if score > best_tok_score:
                        best_tok_score = score
                if best_tok_score * 100 < FUZZY_TOKEN_THRESHOLD:
                    best_tok_score = 0.0
                matched_weight += token_weights[idx] * best_tok_score

            phrase_score = matched_weight / total_weight

            if phrase_score > best['score']:
                best['score'] = phrase_score
                best['intent'] = intent
                best['phrase'] = phrase_obj

    if best['intent']:
        intent_confidence = getattr(best['intent'], 'confidence', 0.8) or 0.8
        confidence = round(min(1.0, best['score'] * intent_confidence), 3)

        if confidence >= HIGH_CONFIDENCE:
            intent_type = best['intent'].intent_type or 'AUTO'
            if intent_type.upper() == 'HUMAN':
                try:
                    payload = {'intent': best['intent'].intent_name, 'message': message, 'site_id': site_id}
                    headers = {'X-Webhook-Key': CRM_WEBHOOK_KEY}
                    requests.post(CRM_WEBHOOK_URL, json=payload, headers=headers, timeout=2)
                except Exception:
                    pass

            return {'intent_name': best['intent'].intent_name, 'intent_type': best['intent'].intent_type, 'response': best['intent'].response or random.choice(FALLBACK_MESSAGES), 'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None, 'confidence': confidence}

        if confidence >= CONFIDENCE_THRESHOLD:
            return {'intent_name': best['intent'].intent_name, 'intent_type': best['intent'].intent_type, 'response': f"I think you're asking about {best['intent'].intent_name}. Is that right?", 'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None, 'confidence': confidence}

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

        return {'intent_name': 'UNKNOWN', 'intent_type': 'UNKNOWN', 'response': random.choice(FALLBACK_MESSAGES), 'confidence': confidence}

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

    return {'intent_name': 'UNKNOWN', 'intent_type': 'UNKNOWN', 'response': random.choice(FALLBACK_MESSAGES), 'confidence': 0.0}