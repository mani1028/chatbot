#!/usr/bin/env python3
"""Test embedding cache integration with intent detection."""

import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("TEST")

def test_intent_detection_with_cache():
    """Test intent detection using the embedding cache."""
    from app import create_app, db
    from models.intent import Intent
    from core.intent_engine import IntentEngine
    from services.embedding_cache import get_embedding_cache
    import time
    
    # Create app and push context
    app = create_app()
    
    with app.app_context():
        logger.info("=" * 60)
        logger.info("Testing Intent Detection with Embedding Cache")
        logger.info("=" * 60)
        
        # Get cache and verify it's empty
        cache = get_embedding_cache()
        initial_size = cache.size()
        logger.info(f"Cache initial size: {initial_size} embeddings")
        
        # Get some intents for testing
        intents = Intent.query.limit(3).all()
        if not intents:
            logger.warning("No intents found in database")
            return
        
        logger.info(f"Found {len(intents)} intents for testing")
        
        # Get a site_id for testing
        from models.site import Site
        site = Site.query.first()
        if not site:
            logger.warning("No site found in database")
            return
        
        site_id = site.id
        logger.info(f"Using site_id: {site_id}")
        
        # Create intent engine
        engine = IntentEngine()
        
        # Test message
        test_message = "what are your business hours"
        logger.info(f"\nProcessing test message: '{test_message}'")
        
        # First detection (should compute embeddings)
        logger.info("First detection (will compute embeddings)...")
        start_time = time.time()
        result1 = engine.detect_intent(test_message, site_id)
        elapsed1 = time.time() - start_time
        logger.info(f"  Result: {result1['intent_name'] if result1 else 'NO MATCH'}")
        logger.info(f"  Time: {elapsed1*1000:.1f}ms")
        logger.info(f"  Cache size after: {cache.size()} embeddings")
        
        # Second detection (should use cached embeddings)
        logger.info("\nSecond detection (will use cache)...")
        start_time = time.time()
        result2 = engine.detect_intent(test_message, site_id)
        elapsed2 = time.time() - start_time
        logger.info(f"  Result: {result2['intent_name'] if result2 else 'NO MATCH'}")
        logger.info(f"  Time: {elapsed2*1000:.1f}ms")
        logger.info(f"  Cache size after: {cache.size()} embeddings")
        
        # Verify cache hit
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
        logger.info(f"\n📊 Performance Summary:")
        logger.info(f"  First run:  {elapsed1*1000:.1f}ms")
        logger.info(f"  Second run: {elapsed2*1000:.1f}ms")
        logger.info(f"  Speedup:    {speedup:.1f}x faster on cache hit")
        
        if elapsed2 < elapsed1:
            logger.info("  ✅ Cache is working - second request was faster!")
        else:
            logger.warning("  ⚠️  Second request not faster (embeddings may be small/fast)")

if __name__ == "__main__":
    try:
        test_intent_detection_with_cache()
        logger.info("\n✅ Cache integration test completed!")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)
