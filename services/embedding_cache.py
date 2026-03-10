"""
Intent Embedding Cache
Stores and reuses pre-computed embeddings for known intents to avoid recomputation.
"""

import json
import logging
import os
import hashlib
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / '.cache'
CACHE_FILE = CACHE_DIR / 'intent_embeddings.json'


class EmbeddingCache:
    """In-memory + disk-based cache for intent embeddings"""
    
    def __init__(self):
        self.memory_cache = {}  # {intent_name: embedding_array}
        self.load_from_disk()
    
    def load_from_disk(self):
        """Load cached embeddings from disk if available"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.memory_cache = json.load(f)
                logger.info(f"Loaded {len(self.memory_cache)} cached embeddings from disk")
            except Exception as e:
                logger.warning(f"Failed to load embedding cache from disk: {e}")
    
    def save_to_disk(self):
        """Save memory cache to disk"""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.memory_cache, f, indent=2)
            logger.debug(f"Saved {len(self.memory_cache)} embeddings to disk")
        except Exception as e:
            logger.warning(f"Failed to save embedding cache to disk: {e}")
    
    def get(self, intent_name: str):
        """Get cached embedding for intent"""
        if intent_name in self.memory_cache:
            return self.memory_cache[intent_name]
        return None
    
    def set(self, intent_name: str, embedding):
        """Cache embedding for intent (as list for serialization)"""
        # Convert to list if it's a numpy array or tensor
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
        
        self.memory_cache[intent_name] = embedding
    
    def batch_cache(self, intent_embeddings: dict):
        """Cache multiple intent embeddings at once"""
        for intent_name, embedding in intent_embeddings.items():
            self.set(intent_name, embedding)
        self.save_to_disk()
    
    def clear(self):
        """Clear all cached embeddings"""
        self.memory_cache.clear()
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        logger.info("Embedding cache cleared")
    
    def size(self):
        """Return number of cached embeddings"""
        return len(self.memory_cache)


# Global instance
_embedding_cache = EmbeddingCache()


def get_embedding_cache() -> EmbeddingCache:
    """Get global embedding cache instance"""
    return _embedding_cache


def precompute_all_intent_embeddings(app=None, model=None):
    """
    Precompute embeddings for all intents in the database.
    Call once at startup or when intents change.
    
    Args:
        app: Flask app instance (optional, will get current_app if not provided)
        model: SentenceTransformer model (optional, will load if not provided)
    """
    try:
        from database import db
        from models.intent import Intent
        
        # Try to use provided app or current_app
        if app is None:
            try:
                from flask import current_app
                app = current_app._get_current_object()
            except RuntimeError:
                logger.warning("No Flask app context available for embedding precomputation")
                return
        
        with app.app_context():
            # Get all unique intent names
            intents = db.session.query(Intent.intent_name).distinct().all()
            intent_names = [i[0] for i in intents if i[0]]
            
            if not intent_names:
                logger.warning("No intents found to precompute embeddings for")
                return
            
            logger.info(f"Precomputing embeddings for {len(intent_names)} intents...")
            
            # Load model if not provided
            if model is None:
                from core.intent_engine import get_embedding_model
                model, available = get_embedding_model()
                if not available:
                    logger.error("Model not available, cannot precompute embeddings")
                    return
            
            # Compute embeddings
            embeddings = model.encode(intent_names, show_progress_bar=False)
            logger.info(f"Computed {len(embeddings)} embeddings")
            
            # Cache them
            for intent_name, embedding in zip(intent_names, embeddings):
                _embedding_cache.set(intent_name, embedding)
            
            _embedding_cache.save_to_disk()
            logger.info(f"Cached and saved {len(intent_names)} intent embeddings")
    except Exception as e:
        logger.error(f"Error precomputing embeddings: {e}", exc_info=True)
