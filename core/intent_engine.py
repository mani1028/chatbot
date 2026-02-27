import re
import random
import requests
import logging
from datetime import datetime
from sqlalchemy import or_
from collections import defaultdict

# Core imports
from database import db
from config import CONFIDENCE_THRESHOLD, FALLBACK_MESSAGES, CRM_WEBHOOK_URL, CRM_WEBHOOK_KEY
from core.tokenizer import tokenize, STOP_WORDS
from core.synonyms import canonical, normalize_text

# Updated imports to pull from the models package directly 
# to avoid circular import issues or missing name errors.
from models import Intent, IntentPhrase, UnansweredQuestion

# Fuzzy matching
try:
    from thefuzz import fuzz
except ImportError:
    # Mock fuzz if not installed to prevent crashes, though it should be in requirements.txt
    class fuzz:
        @staticmethod
        def ratio(a, b): return 100 if a == b else 0

# Optional sentence-transformers support
USE_EMBEDDINGS = False
MODEL = None
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    USE_EMBEDDINGS = True
except Exception:
    USE_EMBEDDINGS = False

# Configuration Constants
FUZZY_TOKEN_THRESHOLD = 80
HIGH_CONFIDENCE = 0.85

class IntentEngine:
    """
    Advanced Intent Engine combining weighted token matching, 
    fuzzy logic, and semantic embeddings.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_token_weight(self, token):
        """Heuristic to weight tokens based on importance."""
        if token in STOP_WORDS:
            return 0.2
        if len(token) <= 3:
            return 0.6
        return 1.0

    def detect_intent(self, message: str, site_id: int) -> dict:
        """
        Detect intent for a given site_id and message.
        """
        # Basic guards
        if not message or (not str(site_id).isdigit() and not isinstance(site_id, int)):
            return self._fallback_response(0.0)

        tokens = tokenize(message)
        if not tokens:
            return self._fallback_response(0.0)

        # Load intents for specific site and global intents (site_id = 0)
        intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id)).all()

        best = {
            'intent': None,
            'phrase': None,
            'score': 0.0
        }

        # Handle Semantic Embeddings
        phrase_items = []
        phrase_embeddings = None
        msg_emb = None
        
        if USE_EMBEDDINGS and intents:
            for intent in intents:
                for phrase_obj in intent.phrases:
                    text = (phrase_obj.phrase or '').strip()
                    if text:
                        phrase_items.append((intent, phrase_obj, text))
            try:
                texts = [p[2] for p in phrase_items]
                if texts:
                    phrase_embeddings = MODEL.encode(texts, convert_to_tensor=True)
                    msg_emb = MODEL.encode(message, convert_to_tensor=True)
            except Exception as e:
                self.logger.error(f"Embedding error: {e}")

        # Primary Scoring Loop
        for intent in intents:
            for phrase_obj in intent.phrases:
                phrase_text = phrase_obj.phrase or ''
                p_tokens = tokenize(phrase_text)
                if not p_tokens:
                    continue

                # Token Weighting logic
                token_weights = [self._get_token_weight(t) for t in p_tokens]
                total_weight = sum(token_weights) or 1.0
                matched_weight = 0.0

                for idx, p_tok in enumerate(p_tokens):
                    best_tok_score = 0.0
                    p_can = canonical(p_tok)
                    
                    for u_tok in tokens:
                        u_can = canonical(u_tok)
                        # Exact or canonical synonym match
                        if p_can == u_can:
                            best_tok_score = 1.0
                            break
                        # Fuzzy match on raw tokens
                        score = fuzz.ratio(p_tok, u_tok) / 100.0
                        if score > best_tok_score:
                            best_tok_score = score
                    
                    # Apply fuzzy threshold
                    if best_tok_score * 100 < FUZZY_TOKEN_THRESHOLD:
                        best_tok_score = 0.0
                    
                    matched_weight += token_weights[idx] * best_tok_score

                phrase_score = matched_weight / total_weight

                # Semantic score integration
                embedding_score = 0.0
                if USE_EMBEDDINGS and phrase_embeddings is not None and msg_emb is not None:
                    try:
                        # Find index for this specific phrase
                        item_idx = next((i for i, it in enumerate(phrase_items) 
                                       if it[1].id == phrase_obj.id), None)
                        if item_idx is not None:
                            sim = st_util.pytorch_cos_sim(msg_emb, phrase_embeddings[item_idx])
                            embedding_score = float(sim.cpu().numpy().flatten()[0])
                            embedding_score = max(0.0, embedding_score)
                    except Exception:
                        pass

                # Calculate combined score (prefer max or weighted average)
                combined_score = phrase_score
                if embedding_score > 0:
                    # Semantic weight: 75% embedding, 25% token overlap
                    combined_score = max(phrase_score, round(0.75 * embedding_score + 0.25 * phrase_score, 3))

                if combined_score > best['score']:
                    best['score'] = combined_score
                    best['intent'] = intent
                    best['phrase'] = phrase_obj

        # Process Results
        if best['intent']:
            intent_conf_multiplier = getattr(best['intent'], 'confidence', 0.8) or 0.8
            final_confidence = round(min(1.0, best['score'] * intent_conf_multiplier), 3)

            # High Confidence: Direct Answer + Action Hooks
            if final_confidence >= HIGH_CONFIDENCE:
                self._handle_handoffs(best['intent'], message, site_id)
                return {
                    'intent_name': best['intent'].intent_name,
                    'intent_type': best['intent'].intent_type,
                    'response': best['intent'].response or random.choice(FALLBACK_MESSAGES),
                    'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None,
                    'confidence': final_confidence
                }

            # Medium Confidence: Suggestion
            if final_confidence >= CONFIDENCE_THRESHOLD:
                return {
                    'intent_name': best['intent'].intent_name,
                    'intent_type': best['intent'].intent_type,
                    'response': f"I think you're asking about {best['intent'].intent_name}. Is that right?",
                    'handoff': None,
                    'confidence': final_confidence
                }

            # Log unanswered if below threshold
            self._log_unanswered(message)
            return self._fallback_response(final_confidence)

        # No intent found at all
        self._log_unanswered(message)
        return self._fallback_response(0.0)

    def _fallback_response(self, confidence):
        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'response': random.choice(FALLBACK_MESSAGES),
            'confidence': confidence
        }

    def _handle_handoffs(self, intent_obj, message, site_id):
        """Triggers external webhooks for human/lead intents."""
        intent_type = (intent_obj.intent_type or 'AUTO').upper()
        if intent_type == 'HUMAN':
            try:
                payload = {
                    'intent': intent_obj.intent_name,
                    'message': message,
                    'site_id': site_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                headers = {'X-Webhook-Key': CRM_WEBHOOK_KEY}
                requests.post(CRM_WEBHOOK_URL, json=payload, headers=headers, timeout=2)
            except Exception as e:
                self.logger.error(f"CRM Webhook failed: {e}")

    def _log_unanswered(self, message):
        """Persists queries that the bot couldn't answer for future training."""
        try:
            q = UnansweredQuestion.query.filter_by(question=message).first()
            if q:
                q.times_asked = (q.times_asked or 1) + 1
                q.last_asked = datetime.utcnow()
            else:
                q = UnansweredQuestion(question=message, times_asked=1, last_asked=datetime.utcnow())
                db.session.add(q)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to log unanswered question: {e}")

# Global instance for easy import
_engine = IntentEngine()
def detect_intent(message: str, site_id: int) -> dict:
    return _engine.detect_intent(message, site_id)