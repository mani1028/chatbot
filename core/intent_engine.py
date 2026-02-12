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

# Fuzzy match threshold for token-level fuzzy matching (0-100)
FUZZY_TOKEN_THRESHOLD = 80
# Tiered confidence cutoff
HIGH_CONFIDENCE = 0.85

# Optional sentence-transformers support (used if installed). Falls back gracefully.
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

    Returns:
    {
      intent_name,
      intent_type,
      response,
      confidence
    }
    """
    # Basic guard
    if not message or not str(site_id).isdigit() and not isinstance(site_id, int):
        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'response': random.choice(FALLBACK_MESSAGES),
            'confidence': 0.0
        }

    tokens = tokenize(message)
    if not tokens:
        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'response': random.choice(FALLBACK_MESSAGES),
            'confidence': 0.0
        }
    # Load intents for the site and global (site_id = 0)
    intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id)).all()

    best = {
        'intent': None,
        'phrase': None,
        'score': 0.0
    }

    # Prepare semantic embeddings for phrases and message if available
    phrase_items = []
    phrase_embeddings = None
    msg_emb = None
    if USE_EMBEDDINGS:
        for intent in intents:
            for phrase_obj in intent.phrases:
                text = (phrase_obj.phrase or '').strip()
                phrase_items.append((intent, phrase_obj, text))
        try:
            texts = [p[2] for p in phrase_items if p[2]]
            if texts:
                phrase_embeddings = MODEL.encode(texts, convert_to_tensor=True)
                msg_emb = MODEL.encode(message, convert_to_tensor=True)
        except Exception:
            phrase_embeddings = None
            msg_emb = None

    # Score each phrase using weighted token matching, synonyms and fuzzy matching
    for intent in intents:
        for phrase_obj in intent.phrases:
            phrase = phrase_obj.phrase or ''
            p_tokens = tokenize(phrase)
            if not p_tokens:
                continue

            # Compute token weights (heuristic): stop-words low weight, others higher
            token_weights = []
            for t in p_tokens:
                if t in STOP_WORDS:
                    token_weights.append(0.2)
                elif len(t) <= 3:
                    token_weights.append(0.6)
                else:
                    token_weights.append(1.0)

            total_weight = sum(token_weights) or 1.0
            matched_weight = 0.0

            for idx, p_tok in enumerate(p_tokens):
                best_tok_score = 0.0
                p_can = canonical(p_tok)
                for u_tok in tokens:
                    u_can = canonical(u_tok)
                    # exact or canonical synonym match
                    if p_can == u_can:
                        best_tok_score = 1.0
                        break
                    # fuzzy match on raw tokens
                    score = fuzz.ratio(p_tok, u_tok) / 100.0
                    if score > best_tok_score:
                        best_tok_score = score
                # apply threshold: treat very low fuzzy matches as zero
                if best_tok_score * 100 < FUZZY_TOKEN_THRESHOLD:
                    best_tok_score = 0.0

                matched_weight += token_weights[idx] * best_tok_score

            phrase_score = matched_weight / total_weight

            # Compute embedding similarity if available
            embedding_score = 0.0
            if USE_EMBEDDINGS and phrase_embeddings is not None and msg_emb is not None:
                try:
                    # find index for this phrase in phrase_items
                    idx = None
                    for i, it in enumerate(phrase_items):
                        if it[0].id == intent.id and it[1].id == phrase_obj.id:
                            idx = i
                            break
                    if idx is not None and idx < len(phrase_embeddings):
                        sim = st_util.pytorch_cos_sim(msg_emb, phrase_embeddings[idx])
                        embedding_score = float(sim.cpu().numpy().flatten()[0])
                        if embedding_score < 0:
                            embedding_score = 0.0
                except Exception:
                    embedding_score = 0.0

            # Combine token-based phrase_score with semantic embedding_score
            combined_score = phrase_score
            if embedding_score:
                combined_score = max(phrase_score, round(0.75 * embedding_score + 0.25 * phrase_score, 3))

            if combined_score > best['score']:
                best['score'] = combined_score
                best['intent'] = intent
                best['phrase'] = phrase_obj

    # If we found a candidate, scale by intent's configured confidence
    if best['intent']:
        # use intent's stored confidence if present, otherwise default
        intent_confidence = getattr(best['intent'], 'confidence', 0.8) or 0.8
        confidence = round(min(1.0, best['score'] * intent_confidence), 3)

        # High confidence -> direct answer
        if confidence >= HIGH_CONFIDENCE:
            # If intent type requires handoff actions, attempt them
            intent_type = best['intent'].intent_type or 'AUTO'
            # Notify CRM for HUMAN intents (best-effort)
            if intent_type.upper() == 'HUMAN':
                try:
                    payload = {
                        'intent': best['intent'].intent_name,
                        'message': message,
                        'site_id': site_id,
                    }
                    headers = {'X-Webhook-Key': CRM_WEBHOOK_KEY}
                    requests.post(CRM_WEBHOOK_URL, json=payload, headers=headers, timeout=2)
                except Exception:
                    pass

            return {
                'intent_name': best['intent'].intent_name,
                'intent_type': best['intent'].intent_type,
                'response': best['intent'].response or random.choice(FALLBACK_MESSAGES),
                'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None,
                'confidence': confidence
            }

        # Medium confidence -> confirm intent with user
        if confidence >= CONFIDENCE_THRESHOLD:
            return {
                'intent_name': best['intent'].intent_name,
                'intent_type': best['intent'].intent_type,
                'response': f"I think you're asking about {best['intent'].intent_name}. Is that right?",
                'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None,
                'confidence': confidence
            }

        # Below threshold -> log unanswered for training and fallback
        try:
            # find existing unanswered record
            q = UnansweredQuestion.query.filter_by(question=message).first()
            if q:
                q.times_asked = (q.times_asked or 1) + 1
                q.last_asked = datetime.utcnow()
            else:
                q = UnansweredQuestion(question=message)
                db.session.add(q)
            db.session.commit()
        except Exception:
            # Logging should not break runtime
            db.session.rollback()

        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'response': random.choice(FALLBACK_MESSAGES),
            'confidence': confidence
        }

    # No candidate found at all
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

    return {
        'intent_name': 'UNKNOWN',
        'intent_type': 'UNKNOWN',
        'response': random.choice(FALLBACK_MESSAGES),
        'confidence': 0.0
    }
