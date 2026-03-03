#!/usr/bin/env python3
"""
COST MEASUREMENT - REALISTIC (respects rate limits)

Send 50 messages across 5 minute windows to measure:
- LLM call rate
- Latency distribution
- Cost per request
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3
import time

app = create_app()

# Get site key
site_key = None
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()
cursor.execute("SELECT public_key FROM sites LIMIT 1")
result = cursor.fetchone()
if result:
    site_key = result[0]
conn.close()

# Realistic mixed-intent messages
TEST_MESSAGES = [
    "How do I reset my password?",
    "I can't log into my account",
    "Where can I find my invoice?",
    "The app keeps crashing",
    "Getting an error on the dashboard",
    "Can I export data to CSV",
    "Do you support Slack integration?",
    "This is ridiculous, nothing works!",
    "What's the weather today?",
    "What's 2+2?",
]

print("COST MEASUREMENT - REALISTIC (50 messages)")
print("=" * 80)

with app.app_context():
    baseline_metrics = db.session.query(Phase1Metrics).count()

print(f"\nBaseline metrics: {baseline_metrics}")
print("[SENDING 50 MESSAGES]")

latencies = []
start_time = time.time()

for i in range(50):
    message = TEST_MESSAGES[i % len(TEST_MESSAGES)]
    session_id = f'cost-real-{i // 10}'
    
    with app.test_client() as client:
        req_start = time.time()
        payload = {
            'message': message,
            'session_id': session_id,
            'site_key': site_key,
            'page_url': 'http://localhost/test'
        }
        
        response = client.post('/api/chat', json=payload)
        req_latency = time.time() - req_start
        latencies.append(req_latency)
        
        status = "200" if response.status_code == 200 else str(response.status_code)
        if (i + 1) % 10 == 0:
            print(f"  Completed {i+1}/50: {status} ({req_latency:.2f}s)")

total_elapsed = time.time() - start_time

print(f"\n[RESULTS]")
with app.app_context():
    final_metrics = db.session.query(Phase1Metrics).count()
    
    # Get metrics data
    all_metrics = db.session.query(Phase1Metrics).filter(Phase1Metrics.id > baseline_metrics).all()
    
    inserted = final_metrics - baseline_metrics
    llm_calls = len([m for m in all_metrics if m.llm_called == 1])
    clarifications = len([m for m in all_metrics if m.clarification_triggered == 1])

print(f"Baseline metrics: {baseline_metrics}")
print(f"Final metrics: {final_metrics}")
print(f"Inserted: {inserted}")
print(f"Total duration: {total_elapsed:.2f}s")
print(f"Avg per message: {total_elapsed/50:.3f}s")

print(f"\n[LATENCY ANALYSIS]")
print(f"Min: {min(latencies):.3f}s")
print(f"Max: {max(latencies):.3f}s")
print(f"Avg: {sum(latencies)/len(latencies):.3f}s")
print(f"Median: {sorted(latencies)[len(latencies)//2]:.3f}s")

print(f"\n[TELEMETRY]")
print(f"LLM Calls: {llm_calls} / {inserted} ({llm_calls/inserted*100:.1f}%)")
print(f"Clarifications: {clarifications} ({clarifications/inserted*100:.1f}%)")

# Cost estimate
est_input_tokens = llm_calls * 200
est_output_tokens = llm_calls * 100
est_cost = (est_input_tokens * 0.01 / 1000) + (est_output_tokens * 0.03 / 1000)

print(f"\n[COST]")
print(f"Est. LLM tokens: {est_input_tokens + est_output_tokens:,}")
print(f"Est. cost: ${est_cost:.4f}")
print(f"Cost per request: ${est_cost/50:.6f}")

print("\n" + "=" * 80)
