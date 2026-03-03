#!/usr/bin/env python
"""
Production server launcher using waitress (Windows-compatible).
Simulates multi-worker behavior with threaded workers.

Usage: python run_production.py
"""
from waitress import serve
from app import app
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    print("=" * 80)
    print("[PRODUCTION SERVER] Starting Waitress WSGI server")
    print("=" * 80)
    print("Configuration:")
    print("  Host: 127.0.0.1")
    print("  Port: 5000")
    print("  Threads: 4 (per worker)")
    print("  Workers: 1 (waitress manages thread pool)")
    print("=" * 80)
    print()
    
    # Waitress configuration:
    # - _app: Flask app instance
    # - host: bind address
    # - port: bind port
    # - threads: number of worker threads (analogous to gunicorn workers)
    # - _quiet: reduce verbosity
    serve(
        app,
        host='127.0.0.1',
        port=5000,
        threads=4,  # Equivalent to 4 worker threads
        _quiet=False
    )
