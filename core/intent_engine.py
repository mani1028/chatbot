import re
import random
import requests
import logging
from datetime import datetime
from sqlalchemy import or_
from collections import defaultdict
import aiohttp
import asyncio
import threading

# Core imports
from database import db
from config import classify_confidence, HIGH_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD, FALLBACK_MESSAGES, CRM_WEBHOOK_URL, CRM_WEBHOOK_KEY
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
_USE_EMBEDDINGS = False
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False

# st_util will be imported lazily only when embeddings are actually used
st_util = None

def get_embedding_model():
    """Lazy-load SentenceTransformer model. Returns (model, available) tuple."""
    global _MODEL, _USE_EMBEDDINGS, _MODEL_LOAD_ATTEMPTED
    
    # Check if embeddings are disabled via environment variable
    import os
    if os.getenv('DISABLE_EMBEDDINGS', 'false').lower() == 'true':
        _USE_EMBEDDINGS = False
        return None, False
    
    if _MODEL is not None:
        return _MODEL, True
    
    if _MODEL_LOAD_ATTEMPTED:
        return None, False
    
    _MODEL_LOAD_ATTEMPTED = True
    
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        _USE_EMBEDDINGS = True
        logging.info("SentenceTransformer model loaded successfully")
        return _MODEL, True
    except Exception as e:
        logging.error(f"Failed to load SentenceTransformer model: {e}")
        _USE_EMBEDDINGS = False
        return None, False


# Configuration Constants
FUZZY_TOKEN_THRESHOLD = 80

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

    async def send_crm_webhook(self, payload, headers):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(CRM_WEBHOOK_URL, json=payload, headers=headers, timeout=2) as response:
                    if response.status != 200:
                        self.logger.error(f"CRM Webhook failed with status {response.status}")
            except Exception as e:
                self.logger.error(f"CRM Webhook failed: {e}")

    async def _handle_handoffs(self, intent_name, intent_type, message, site_id):
        """Triggers external webhooks for human/lead intents."""
        intent_type = (intent_type or 'AUTO').upper()
        if intent_type in ('HUMAN', 'LEAD'):  # Also fixed to support LEAD webhooks!
            payload = {
                'intent': intent_name,
                'message': message,
                'site_id': site_id
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': CRM_WEBHOOK_KEY
            }
            await self.send_crm_webhook(payload, headers)

    def detect_intent(self, message: str, site_id: int, history: list = None) -> dict:
        """
        Detect intent for a given site_id and message.
        """

        # Basic guards
        if not message or (not str(site_id).isdigit() and not isinstance(site_id, int)):
            return self._fallback_response(0.0)

        # Tokenize ONLY the current message for intent scoring
        # (Mixing history into the raw tokens causes previous intents to trigger infinitely)
        tokens = tokenize(message)
        if not tokens:
            return self._fallback_response(0.0)

        # If you still want full context specifically for the Semantic Embeddings (LLM), 
        # keep it isolated to a separate variable:
        full_context = ' '.join([h['user_message'] for h in history]) + ' ' + message if history else message

        # Load intents for specific site and global intents (site_id = 0)
        intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id)).all()

        # Handle medium confidence responses
        if history and history[-1].get('intent_name') == 'clarification':
            if message.lower() in ['yes', 'yeah', 'yep']:
                return self._fallback_response(0.0)
            elif message.lower() in ['no', 'nope']:
                return self._fallback_response(0.0)

        best = {
            'intent': None,
            'phrase': None,
            'score': 0.0,
            'weight': 0.0    # Add weight tracker to resolve ties
        }

        # Handle Semantic Embeddings
        phrase_items = []
        phrase_embeddings = None
        msg_emb = None
        
        model, embeddings_available = get_embedding_model()
        if embeddings_available and intents:
            from services.embedding_cache import get_embedding_cache
            import torch
            import numpy as np
            
            cache = get_embedding_cache()
            
            for intent in intents:
                for phrase_obj in intent.phrases.all():
                    text = (phrase_obj.phrase or '').strip()
                    if text:
                        phrase_items.append((intent, phrase_obj, text))
            try:
                texts = [p[2] for p in phrase_items]
                if texts:
                    # Build final phrase embeddings list by checking cache first
                    phrase_embeddings_list = []
                    texts_to_compute = []
                    
                    for text in texts:
                        cache_key = f"phrase_{text}"
                        cached = cache.get(cache_key)
                        if cached is not None:
                            phrase_embeddings_list.append(np.array(cached))
                        else:
                            texts_to_compute.append((text, cache_key))
                            phrase_embeddings_list.append(None)  # Placeholder
                    
                    # Compute missing embeddings
                    if texts_to_compute:
                        texts_only = [t[0] for t in texts_to_compute]
                        computed_embeddings = model.encode(texts_only, convert_to_tensor=False)
                        
                        # Fill in placeholders and cache
                        compute_idx = 0
                        for text_idx, embedding in enumerate(phrase_embeddings_list):
                            if embedding is None:  # This was a cache miss
                                text, cache_key = texts_to_compute[compute_idx]
                                emb = computed_embeddings[compute_idx]
                                cache.set(cache_key, emb)
                                phrase_embeddings_list[text_idx] = np.array(emb)
                                compute_idx += 1
                    
                    # Convert to tensor
                    phrase_embeddings_array = np.array(phrase_embeddings_list)
                    phrase_embeddings = torch.tensor(phrase_embeddings_array, dtype=torch.float32)
                    
                    # Message embedding (cache separately)
                    msg_cache_key = f"msg_{message}"
                    msg_cached = cache.get(msg_cache_key)
                    if msg_cached is not None:
                        msg_emb = torch.tensor(np.array(msg_cached), dtype=torch.float32)
                    else:
                        msg_emb = model.encode(message, convert_to_tensor=True)
                        cache.set(msg_cache_key, msg_emb.cpu().numpy() if hasattr(msg_emb, 'cpu') else msg_emb.numpy())
            except Exception as e:
                self.logger.error(f"Embedding error: {e}")

        # Primary Scoring Loop
        for intent in intents:
            for phrase_obj in intent.phrases.all():
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
                    if round(best_tok_score * 100, 2) <= FUZZY_TOKEN_THRESHOLD:
                        best_tok_score = 0.0
                    
                    matched_weight += token_weights[idx] * best_tok_score

                phrase_score = matched_weight / total_weight

                # Semantic score integration
                embedding_score = 0.0
                if embeddings_available and phrase_embeddings is not None and msg_emb is not None:
                    try:
                        # Lazy import st_util only when needed
                        global st_util
                        if st_util is None:
                            from sentence_transformers import util as st_util_import
                            st_util = st_util_import
                        
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

                # If the score is higher OR if it's a tie but this phrase matched more words
                if combined_score > best['score'] or (combined_score == best['score'] and total_weight > best['weight']):
                    best['score'] = combined_score
                    best['weight'] = total_weight
                    best['intent'] = intent
                    best['phrase'] = phrase_obj

        # Process Results
        if best['intent']:
            intent_conf_multiplier = getattr(best['intent'], 'confidence', 0.8) or 0.8
            final_confidence = round(min(1.0, best['score'] * intent_conf_multiplier), 3)

            # Use single classify_confidence() authority (GATE 2 ENFORCEMENT)
            confidence_class = classify_confidence(final_confidence)

            # High Confidence: Direct Answer + Action Hooks
            if confidence_class == "HIGH":
                # RUN IN BACKGROUND THREAD TO PREVENT 2-SECOND BLOCKING
                threading.Thread(
                    target=lambda: asyncio.run(self._handle_handoffs(
                        best['intent'].intent_name, 
                        best['intent'].intent_type, 
                        message, 
                        site_id
                    ))
                ).start()
                
                return {
                    'intent_name': best['intent'].intent_name,
                    'intent_type': best['intent'].intent_type,
                    'response': best['intent'].response or random.choice(FALLBACK_MESSAGES),
                    'handoff': best['intent'].intent_type if best['intent'].intent_type in ('LEAD', 'HUMAN') else None,
                    'confidence': final_confidence
                }

            # Medium Confidence: Suggestion
            if confidence_class == "MEDIUM":
                # Clean up the snake_case name for the user
                clean_name = best['intent'].intent_name.replace('_', ' ').title()
                
                return {
                    'intent_name': best['intent'].intent_name,
                    'intent_type': best['intent'].intent_type,
                    'response': f"I think you're asking about {clean_name}. Is that right?",
                    'handoff': None,
                    'confidence': final_confidence
                }

            # Log unanswered if below threshold
            self._log_unanswered(message, site_id)
            return self._fallback_response(final_confidence)

        # No intent found at all
        self._log_unanswered(message, site_id)
        return self._fallback_response(0.0)

    def _fallback_response(self, confidence):
        """Return fallback response - no LLM here, let orchestrator handle it."""
        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'response': random.choice(FALLBACK_MESSAGES),
            'confidence': confidence
        }

    def _log_unanswered(self, message, site_id):
        """Persists queries that the bot couldn't answer for future training."""
        try:
            q = UnansweredQuestion.query.filter_by(question=message, site_id=site_id).first()
            if q:
                q.times_asked = (q.times_asked or 1) + 1
                q.last_asked = datetime.utcnow()
            else:
                q = UnansweredQuestion(question=message, site_id=site_id, times_asked=1, last_asked=datetime.utcnow())
                db.session.add(q)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to log unanswered question: {e}")

# Global instance for easy import
_engine = IntentEngine()
def detect_intent(message: str, site_id: int, history: list = None) -> dict:
    return _engine.detect_intent(message, site_id, history)