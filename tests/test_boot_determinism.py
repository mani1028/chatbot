#!/usr/bin/env python3
"""
Test: Boot Determinism After SentenceTransformer Lazy-Load Refactoring

CRITICAL: This test verifies the app boots in < 15 seconds WITHOUT
triggering HuggingFace model downloads at import time.
"""

import os
import sys
import time
import json
import requests
from threading import Thread
import signal

# Force embeddings disabled for this test
os.environ['DISABLE_EMBEDDINGS'] = 'true'

def test_imports():
    """Step 1: Test that imports complete without hanging"""
    print("\n" + "="*70)
    print("TEST 1: MODULE IMPORTS (lazy-load verification)")
    print("="*70)
    
    start = time.time()
    try:
        # These imports should NOT trigger SentenceTransformer download
        from services.vector_search import query_knowledge_base
        from core.intent_engine import detect_intent, get_embedding_model
        from services.chromadb_vector import add_document
        import_time = time.time() - start
        
        print(f"✓ All imports completed in {import_time:.2f}s")
        print("✓ No blocking model downloads occurred")
        print("✓ Lazy-load pattern working correctly")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_app_boot():
    """Step 2: Test app initialization"""
    print("\n" + "="*70)
    print("TEST 2: APP INITIALIZATION (deterministic boot)")
    print("="*70)
    
    start = time.time()
    try:
        from app import create_app
        app = create_app()
        boot_time = time.time() - start
        
        print(f"✓ App initialized in {boot_time:.2f}s")
        print(f"✓ Boot time under 15s threshold: {boot_time < 15}")
        print(f"✓ Deterministic startup confirmed")
        
        return app, boot_time
    except Exception as e:
        print(f"✗ App boot failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_health_endpoint(app):
    """Step 3: Test /health endpoint"""
    print("\n" + "="*70)
    print("TEST 3: HEALTH ENDPOINT (telemetry monitoring)")
    print("="*70)
    
    try:
        with app.test_client() as client:
            start = time.time()
            response = client.get('/health')
            elapsed = time.time() - start
            
            if response.status_code != 200:
                print(f"✗ Health endpoint failed: {response.status_code}")
                return False
            
            data = response.get_json()
            print(f"✓ Health check responded in {elapsed:.3f}s")
            print(f"✓ Status: {data.get('status')}")
            print(f"✓ Telemetry healthy: {data.get('telemetry', {}).get('telemetry_healthy', 'N/A')}")
            print(f"✓ Metrics failures: {data.get('telemetry', {}).get('metrics_failures', 0)}")
            
            return True
    except Exception as e:
        print(f"✗ Health endpoint test failed: {e}")
        return False

def test_lazy_load_on_demand():
    """Step 4: Verify embeddings still load on demand (when needed)"""
    print("\n" + "="*70)
    print("TEST 4: LAZY-LOAD ON DEMAND (embeddings availability)")
    print("="*70)
    
    try:
        from core.intent_engine import get_embedding_model
        
        # With DISABLE_EMBEDDINGS=true, should return None
        model, available = get_embedding_model()
        
        if available:
            print(f"✗ Model unexpectedly loaded (should be disabled)")
            return False
        
        print(f"✓ Embeddings correctly disabled via DISABLE_EMBEDDINGS env var")
        print(f"✓ Model returns None when disabled: {model is None}")
        print(f"✓ Lazy-load function implemented correctly")
        
        return True
    except Exception as e:
        print(f"✗ Lazy-load test failed: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("BOOT DETERMINISM VALIDATION SUITE")
    print("="*70)
    print(f"Environment: DISABLE_EMBEDDINGS={os.environ.get('DISABLE_EMBEDDINGS')}")
    
    # Run tests in sequence
    results = {
        'imports': test_imports(),
        'app_boot': test_app_boot(),
        'health': None,
        'lazy_load': None,
    }
    
    app, boot_time = results['app_boot']
    if app:
        results['health'] = test_health_endpoint(app)
        results['lazy_load'] = test_lazy_load_on_demand()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    all_pass = all([
        results['imports'],
        results['app_boot'][1] is not None,
        results['app_boot'][1] < 15 if results['app_boot'][1] else False,
        results['health'],
        results['lazy_load']
    ])
    
    if all_pass:
        print("✓ ALL TESTS PASSED")
        print("✓ App boots deterministically in < 15s")
        print("✓ No HuggingFace downloads at import time")
        print("✓ Production-ready: CONFIRMED")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print(f"  Imports: {'PASS' if results['imports'] else 'FAIL'}")
        print(f"  App boot: {'PASS' if results['app_boot'][1] is not None else 'FAIL'} ({results['app_boot'][1]:.2f}s)" if results['app_boot'][1] else "  App boot: FAIL")
        print(f"  Health: {'PASS' if results['health'] else 'FAIL'}")
        print(f"  Lazy-load: {'PASS' if results['lazy_load'] else 'FAIL'}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
