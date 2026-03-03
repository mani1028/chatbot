#!/usr/bin/env python3
"""
PASS 3: CONCURRENT REQUESTS - TELEMETRY INTEGRITY (LIMITER DISABLED)

Verify:
- 50 concurrent requests with rate limiter disabled
- Exactly 50 metrics rows inserted
- No deadlocks
- No partial inserts
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

# Patch limiter before importing app
from unittest import mock
import database

# Create mock limiter that doesn't actually limit
mock_limiter = mock.Mock()
mock_limiter.limit = lambda x: lambda f: f  # Returns decorator that does nothing

# Replace the limiter in database module
original_limiter = database.limiter
database.limiter = mock_limiter

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3
import threading
import time
from queue import Queue

app = create_app()

# Thread-safe request counter
request_queue = Queue()
errors = []

def send_request(request_id):
    """Send single request from worker thread"""
    try:
        site_key = None
        conn = sqlite3.connect('instance/chatbot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT public_key FROM sites LIMIT 1")
        result = cursor.fetchone()
        if result:
            site_key = result[0]
        conn.close()
        
        if not site_key:
            errors.append(f"Request {request_id}: No site key found")
            return
        
        with app.test_client() as client:
            payload = {
                'message': f'PASS 3 concurrent test {request_id}',
                'session_id': f'pass3-concurrent-{request_id}',
                'site_key': site_key,
                'page_url': 'http://localhost/test'
            }
            
            start = time.time()
            response = client.post('/api/chat', json=payload)
            elapsed = time.time() - start
            
            request_queue.put({
                'request_id': request_id,
                'status': response.status_code,
                'elapsed': elapsed
            })
    except Exception as e:
        errors.append(f"Request {request_id}: {str(e)}")

print("PASS 3: CONCURRENT REQUESTS (LIMITER DISABLED)")
print("=" * 80)

# Baseline
print("\n[BASELINE]")
with app.app_context():
    baseline = db.session.query(Phase1Metrics).count()
print(f"Baseline metrics: {baseline}")

# Send 50 concurrent requests
print("\n[SENDING 50 CONCURRENT REQUESTS]")
threads = []
start_time = time.time()

for i in range(50):
    t = threading.Thread(target=send_request, args=(i,))
    threads.append(t)
    t.start()

# Wait for all requests
for t in threads:
    t.join()

elapsed_total = time.time() - start_time
print(f"All 50 requests completed in {elapsed_total:.2f}s")

# Collect results
results = []
while not request_queue.empty():
    results.append(request_queue.get())

results.sort(key=lambda x: x['request_id'])

# Check metrics
print("\n[AFTER 50 REQUESTS]")
with app.app_context():
    final = db.session.query(Phase1Metrics).count()

inserted = final - baseline
print(f"Final metrics: {final}")
print(f"Inserted: {inserted}")

# Validate
succeeded_200 = len([r for r in results if r['status'] == 200])
print("\n[VALIDATION]")
print(f"All 50 succeeded (200): {'PASS' if succeeded_200 == 50 else f'FAIL ({succeeded_200}/50)'}")
print(f"Inserted count = 50: {'PASS' if inserted == 50 else f'FAIL ({inserted}/50)'}")
print(f"No errors: {'PASS' if len(errors) == 0 else f'FAIL ({len(errors)} errors)'}")

# Show timing
avg_time = sum(r['elapsed'] for r in results) / len(results) if results else 0
max_time = max(r['elapsed'] for r in results) if results else 0
min_time = min(r['elapsed'] for r in results) if results else 0

print(f"\n[TIMING]")
print(f"Total duration: {elapsed_total:.2f}s")
print(f"Avg per request: {avg_time:.3f}s")
print(f"Min: {min_time:.3f}s, Max: {max_time:.3f}s")
print(f"Concurrent throughput: {50/elapsed_total:.1f} req/s")

if errors:
    print(f"\n[ERRORS] (showing first 5)")
    for error in errors[:5]:
        print(f"  {error}")

print("\n" + "=" * 80)
print("PASS 3 DATA")
print(f"Baseline: {baseline}")
print(f"Final: {final}")
print(f"Inserted: {inserted}")
print(f"Requests Status 200: {succeeded_200} / 50")
print(f"Total Duration: {elapsed_total:.2f}s")
print(f"Concurrent Rate: {50/elapsed_total:.1f} req/s")
if succeeded_200 == 50 and inserted == 50:
    print("\n✓ PASS 3 VALIDATED")
    print("  - 50 concurrent requests")
    print("  - 50 metrics rows inserted")
    print("  - No errors or deadlocks")
else:
    print(f"\n✗ PASS 3 INCOMPLETE")
    print(f"  - Status 200: {succeeded_200}/50")
    print(f"  - Inserted: {inserted}/50")
print("=" * 80)
