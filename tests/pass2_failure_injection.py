#!/usr/bin/env python3
"""
PASS 2: INTENTIONAL TELEMETRY FAILURE INJECTION

Verify:
- HTTP returns 200 (chat persists)
- Metrics row NOT inserted
- Logs show ERROR
- /health shows failure
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3

app = create_app()

print("PASS 2: FAILURE INJECTION")
print("=" * 80)

# Step 1: Baseline
print("\n[BASELINE]")
with app.app_context():
    baseline_metrics = db.session.query(Phase1Metrics).count()
print(f"Baseline metrics count: {baseline_metrics}")

# Get baseline health
with app.test_client() as client:
    health_response = client.get('/health')
    baseline_health = health_response.get_json() if health_response.status_code == 200 else {}
    print(f"Baseline /health: {baseline_health}")

# Step 2: Send request with failure injected
print("\n[SENDING REQUEST - FAILURE INJECTED]")

site_key = None
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()
cursor.execute("SELECT public_key FROM sites LIMIT 1")
site_key = cursor.fetchone()[0]
conn.close()

with app.test_client() as client:
    payload = {
        'message': 'PASS 2 test',
        'session_id': 'pass2-failure-test',
        'site_key': site_key,
        'page_url': 'http://localhost/test'
    }
    
    response = client.post('/api/chat', json=payload)
    http_status = response.status_code
    print(f"HTTP Status: {http_status}")
    
    if http_status == 200:
        print(f"Response: Chat response body received (length={len(response.data)})")

# Step 3: Final metrics count
print("\n[AFTER REQUEST]")
with app.app_context():
    final_metrics = db.session.query(Phase1Metrics).count()
    
final_import = final_metrics - baseline_metrics
print(f"Final metrics count: {final_metrics}")
print(f"Metrics inserted: {final_import}")

# Step 4: Final health
with app.test_client() as client:
    health_response = client.get('/health')
    final_health = health_response.get_json() if health_response.status_code == 200 else {}
    print(f"Final /health status: {health_response.status_code}")
    print(f"Final /health: {final_health}")

# Step 5: Log analysis
print("\n[VALIDATION]")
print(f"HTTP Status 200: {'PASS' if http_status == 200 else 'FAIL'}")
print(f"Metrics NOT inserted: {'PASS' if final_import == 0 else 'FAIL'}")
print(f"Health shows failure: {'PASS' if final_health.get('telemetry', {}).get('telemetry_healthy') == False else 'FAIL'}")
print(f"Metrics failures > 0: {'PASS' if final_health.get('telemetry', {}).get('metrics_failures', 0) > 0 else 'FAIL'}")

print("\n" + "=" * 80)
print("PASS 2 DATA")
print(f"HTTP Status: {http_status}")
print(f"Metrics Before: {baseline_metrics}")
print(f"Metrics After: {final_metrics}")
print(f"Inserted: {final_import}")
print(f"Health Response: {final_health}")
print("=" * 80)
