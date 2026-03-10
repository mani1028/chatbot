#!/usr/bin/env python3
"""Test embedding cache functionality."""

import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def test_cache_basic():
    """Test basic cache operations."""
    from services.embedding_cache import EmbeddingCache
    import numpy as np
    
    logger.info("Testing basic cache operations...")
    cache = EmbeddingCache()
    
    # Test set and get
    test_embedding = np.array([0.1, 0.2, 0.3, 0.4])
    cache.set("test_key", test_embedding)
    
    retrieved = cache.get("test_key")
    assert retrieved is not None, "Failed to retrieve cached embedding"
    assert len(retrieved) == 4, f"Expected 4 dims, got {len(retrieved)}"
    logger.info("✓ Basic cache operations work")

def test_model_availability():
    """Test if embedding model is available."""
    from core.intent_engine import get_embedding_model
    
    logger.info("Testing embedding model availability...")
    model, available = get_embedding_model()
    
    if available:
        logger.info("✓ Embedding model is available")
        # Try encoding a simple text
        test_text = "hello world"
        embedding = model.encode(test_text, convert_to_tensor=False)
        logger.info(f"✓ Model can encode text (embedding shape: {embedding.shape})")
    else:
        logger.warning("⚠ Embedding model not available (expected if first run)")

def test_cache_with_model():
    """Test caching with actual model."""
    from core.intent_engine import get_embedding_model
    from services.embedding_cache import EmbeddingCache
    
    logger.info("Testing cache with model encoding...")
    
    model, available = get_embedding_model()
    if not available:
        logger.warning("Skipping model test - model not available")
        return
    
    cache = EmbeddingCache()
    
    # Encode two phrases
    phrases = ["hello", "goodbye"]
    embeddings = model.encode(phrases, convert_to_tensor=False)
    
    # Cache them
    for phrase, emb in zip(phrases, embeddings):
        cache.set(f"phrase_{phrase}", emb)
    
    # Retrieve and verify
    for phrase in phrases:
        key = f"phrase_{phrase}"
        cached = cache.get(key)
        assert cached is not None, f"Failed to retrieve {key}"
        logger.info(f"✓ Cached and retrieved: {key}")

if __name__ == "__main__":
    try:
        test_cache_basic()
        test_model_availability()
        test_cache_with_model()
        logger.info("\n✅ All cache tests passed!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)
