"""
Model preloading utility for serverless/cold-start optimization.
Preloads SentenceTransformer model at app startup to avoid delays on first request.
"""
import os
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Flag to track preload status
_PRELOAD_STARTED = False
_PRELOAD_COMPLETE = False
_PRELOAD_ERROR = None

def preload_models_async(app=None):
    """
    Preload SentenceTransformer model in a background thread.
    Non-blocking; allows app to start while model downloads.
    
    Args:
        app: Flask app instance (optional, for app context if needed)
    """
    global _PRELOAD_STARTED, _PRELOAD_COMPLETE, _PRELOAD_ERROR
    
    if _PRELOAD_STARTED:
        return
    
    _PRELOAD_STARTED = True
    
    def _load():
        global _PRELOAD_COMPLETE, _PRELOAD_ERROR
        try:
            # Check if embeddings are disabled
            if os.getenv('DISABLE_EMBEDDINGS', 'false').lower() == 'true':
                logger.info("Model preload skipped: DISABLE_EMBEDDINGS=true")
                _PRELOAD_COMPLETE = True
                return
            
            logger.info("Starting background model preload...")
            start_time = time.time()
            
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            elapsed = time.time() - start_time
            logger.info(f"✓ SentenceTransformer model preloaded in {elapsed:.2f}s")
            _PRELOAD_COMPLETE = True
            
        except Exception as e:
            _PRELOAD_ERROR = e
            logger.error(f"✗ Failed to preload model: {e}")
            _PRELOAD_COMPLETE = True
    
    # Start in daemon thread so it doesn't block app shutdown
    thread = threading.Thread(target=_load, daemon=True)
    thread.start()


def preload_models_blocking(timeout=300):
    """
    Synchronously preload SentenceTransformer model with timeout.
    Blocks until model is loaded or timeout expires.
    
    Args:
        timeout: Maximum seconds to wait for preload (default: 5 minutes)
    
    Returns:
        bool: True if preload succeeded, False if disabled or timed out
    """
    global _PRELOAD_STARTED, _PRELOAD_COMPLETE, _PRELOAD_ERROR
    
    # Check if embeddings are disabled
    if os.getenv('DISABLE_EMBEDDINGS', 'false').lower() == 'true':
        logger.info("Model preload skipped: DISABLE_EMBEDDINGS=true")
        return True
    
    if not _PRELOAD_STARTED:
        preload_models_async()
    
    # Wait for preload to complete
    start_time = time.time()
    while not _PRELOAD_COMPLETE:
        if time.time() - start_time > timeout:
            logger.warning(f"Model preload timed out after {timeout}s")
            return False
        time.sleep(0.1)
    
    if _PRELOAD_ERROR:
        logger.error(f"Model preload failed: {_PRELOAD_ERROR}")
        return False
    
    logger.info("Model preload complete and verified")
    return True


def is_model_ready():
    """
    Check if model preload has completed.
    
    Returns:
        bool: True if preload finished (success or failure)
    """
    return _PRELOAD_COMPLETE


def get_preload_error():
    """
    Get any error from model preloading.
    
    Returns:
        Exception or None
    """
    return _PRELOAD_ERROR
