#!/usr/bin/env python3
"""
COST MEASUREMENT SIMULATION

600 realistic mixed-intent messages to measure:
- LLM call rate
- Clarification trigger rate
- Token consumption
- Per-request latency
- Cost delta vs baseline
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
from models.chat_log import ChatLog
import sqlite3
import time
import threading
from queue import Queue
from datetime import datetime

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

# Realistic mixed-intent messages (users naturally arrive with varied purposes)
TEST_MESSAGES = [
    # Information/Help (30%)
    ("How do I reset my password?", "password_help"),
    ("I can't log into my account", "login_issue"),
    ("Where can I find my invoice?", "invoice_query"),
    ("What's the refund policy?", "policy_query"),
    ("I need help with billing", "billing_help"),
    ("How do I cancel my subscription?", "subscription_help"),
    
    # Technical (25%)
    ("The app keeps crashing", "technical_issue"),
    ("Getting an error on the dashboard", "error_report"),
    ("The API endpoint is slow", "performance_issue"),
    ("Mobile app not working", "mobile_issue"),
    
    # Business/Feature Requests (25%)
    ("Can I export data to CSV", "feature_request"),
    ("Do you support integrations with Slack?", "integration_query"),
    ("How many users can I add to my team?", "limits_query"),
    ("What's in the Pro plan?", "pricing_query"),
    
    # Emotional/Frustrated (10%)
    ("This is ridiculous, nothing works!", "frustration"),
    ("I'm very upset with your service", "complaint"),
    ("Why is this so hard?", "frustration"),
    
    # Nonsense/Off-topic (10%)
    ("What's the weather today?", "off_topic"),
    ("Tell me a joke", "off_topic"),
    ("What's 2+2?", "off_topic"),
]

print("COST MEASUREMENT SIMULATION")
print("=" * 80)
print("\n[TEST CONFIGURATION]")
print(f"Total messages: 600")
print(f"Unique distinct messages: {len(TEST_MESSAGES)}")
print(f"Repetition factor: {600 // len(TEST_MESSAGES)} cycles")

# Metrics
baseline_metrics = None
metrics_by_session = []
llm_calls = 0
clarifications = 0
start_time = time.time()

with app.app_context():
    baseline_metrics = db.session.query(Phase1Metrics).count()

print(f"Baseline metrics count: {baseline_metrics}")

# Send 600 messages (sequential for stability)
print("\n[SENDING 600 MESSAGES]")
for cycle in range(600 // len(TEST_MESSAGES)):
    for msg_idx, (message, category) in enumerate(TEST_MESSAGES):
        request_id = cycle * len(TEST_MESSAGES) + msg_idx
        
        with app.test_client() as client:
            payload = {
                'message': message,
                'session_id': f'cost-measure-{request_id // 10}',
                'site_key': site_key,
                'page_url': 'http://localhost/test'
            }
            
            response = client.post('/api/chat', json=payload)
            if response.status_code != 200:
                print(f"Request {request_id}: FAILED ({response.status_code})")
        
        if (request_id + 1) % 100 == 0:
            print(f"  Completed {request_id + 1} / 600 messages")

elapsed = time.time() - start_time

print(f"\n[RESULTS]")
with app.app_context():
    final_metrics = db.session.query(Phase1Metrics).count()
    
    # Count LLM calls
    llm_calls_count = db.session.query(Phase1Metrics).filter_by(llm_called=1).count()
    
    # Count clarifications
    clarifications_count = db.session.query(Phase1Metrics).filter_by(clarification_triggered=1).count()
    
    # Get LOW confidence band count
    low_confidence = db.session.query(Phase1Metrics).filter_by(confidence_band='LOW').count()

inserted = final_metrics - baseline_metrics
llm_rate = (llm_calls_count / inserted * 100) if inserted > 0 else 0
clarification_rate = (clarifications_count / inserted * 100) if inserted > 0 else 0

print(f"Baseline metrics: {baseline_metrics}")
print(f"Final metrics: {final_metrics}")
print(f"Inserted: {inserted}")
print(f"Duration: {elapsed:.2f}s")
print(f"Avg per message: {elapsed/600:.3f}s")
print(f"Throughput: {600/elapsed:.1f} msg/s")

print(f"\n[TELEMET RY DATA]")
print(f"LLM Calls: {llm_calls_count} ({llm_rate:.1f}%)")
print(f"Clarifications: {clarifications_count} ({clarification_rate:.1f}%)")
print(f"LOW Confidence (no LLM): {low_confidence}")

# Estimate costs (OpenRouter API pricing)
# gpt-4-turbo: $0.01/1K input, $0.03/1K output
# Assume ~200 tokens per request, 100 output tokens
est_input_tokens = llm_calls_count * 200
est_output_tokens = llm_calls_count * 100
est_cost = (est_input_tokens * 0.01 / 1000) + (est_output_tokens * 0.03 / 1000)

print(f"\n[COST ESTIMATE]")
print(f"Est. input tokens: {est_input_tokens:,}")
print(f"Est. output tokens: {est_output_tokens:,}")
print(f"Est. LLM cost: ${est_cost:.4f}")
print(f"Cost per request: ${est_cost/600:.6f}")
print(f"Cost per message with LLM: ${est_cost/llm_calls_count:.6f}" if llm_calls_count > 0 else "Cost per message with LLM: N/A")

print("\n" + "=" * 80)
print("COST MEASUREMENT COMPLETE")
print("=" * 80)
