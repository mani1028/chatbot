#!/usr/bin/env python3
"""
PASS 3: CONCURRENT REQUESTS - TELEMETRY INTEGRITY

Verify:
- 50 concurrent requests each insert exactly 1 metrics row
- No deadlocks
- Total inserted = exactly 50
- No partial inserts or duplicates
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3
import threading
import time
import uuid
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

print("PASS 3: CONCURRENT REQUESTS")
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
print("\n[VALIDATION]")
print(f"All 50 succeeded (200): {'PASS' if len([r for r in results if r['status'] == 200]) == 50 else 'FAIL'}")
print(f"Inserted count = 50: {'PASS' if inserted == 50 else 'FAIL'}")
print(f"No errors: {'PASS' if len(errors) == 0 else 'FAIL'}")

# Show timing
avg_time = sum(r['elapsed'] for r in results) / len(results)
max_time = max(r['elapsed'] for r in results)
min_time = min(r['elapsed'] for r in results)

print(f"\n[TIMING]")
print(f"Total duration: {elapsed_total:.2f}s")
print(f"Avg per request: {avg_time:.3f}s")
print(f"Min: {min_time:.3f}s, Max: {max_time:.3f}s")
print(f"Concurrent throughput: {50/elapsed_total:.1f} req/s")

if errors:
    print(f"\n[ERRORS]")
    for error in errors:
        print(f"  {error}")

print("\n" + "=" * 80)
print("PASS 3 DATA")
print(f"Baseline: {baseline}")
print(f"Final: {final}")
print(f"Inserted: {inserted}")
print(f"Requests Status 200: {len([r for r in results if r['status'] == 200])} / 50")
print(f"Total Duration: {elapsed_total:.2f}s")
print(f"Concurrent Rate: {50/elapsed_total:.1f} req/s")
print("=" * 80)
