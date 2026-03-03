#!/usr/bin/env python3
"""
PASS 1 - 5 CONTROLLED TEST MESSAGES

Scenarios:
1. High confidence intent - expect: band=HIGH, llm_called=0
2. Unknown garbage - expect: band=LOW, llm_called=1
3. Mid-band intent - expect: band=MID
4. Clarification confirmation - expect: clarification_confirmed=1
5. Workflow-active case - expect: workflow_active=1

Then query the results.
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3

app = create_app()

print("PASS 1: 5 CONTROLLED TEST MESSAGES")
print("=" * 70)

# Get site key
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()
cursor.execute("SELECT public_key FROM sites LIMIT 1")
site_key = cursor.fetchone()[0]
conn.close()

# Define 5 test scenarios
test_messages = [
    {
        'message': 'What is your refund policy?',
        'description': 'High confidence intent'
    },
    {
        'message': 'xywz mlkjhfsdf qwerty nonsense',
        'description': 'Unknown garbage input'
    },
    {
        'message': 'I need help with my account',
        'description': 'Mid-band intent'
    },
    {
        'message': 'yes',
        'description': 'Clarification confirmation'
    },
    {
        'message': 'create new project',
        'description': 'Workflow-active case'
    }
]

# Send requests
print(f"\nSending {len(test_messages)} test messages:\n")

with app.test_client() as client:
    for i, test in enumerate(test_messages, 1):
        print(f"[{i}] {test['description']}")
        print(f"    Message: {test['message'][:40]}...")
        
        payload = {
            'message': test['message'],
            'session_id': f'test-session-{i}',
            'site_key': site_key,
            'page_url': 'http://localhost/test'
        }
        
        response = client.post('/api/chat', json=payload)
        print(f"    Status: {response.status_code}")

print("\n" + "=" * 70)
print("QUERY RESULTS")
print("=" * 70)

# Query the metrics
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()

# Count aggregate
cursor.execute('''
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN llm_called = 1 THEN 1 ELSE 0 END) as llm_calls,
  SUM(CASE WHEN clarification_triggered = 1 THEN 1 ELSE 0 END) as clarifications,
  SUM(CASE WHEN workflow_active = 1 THEN 1 ELSE 0 END) as workflows
FROM phase1_metrics
''')

result = cursor.fetchone()
print(f"\nAGGREGATE:")
print(f"  Total records: {result[0]}")
print(f"  LLM calls: {result[1]}")
print(f"  Clarifications triggered: {result[2]}")
print(f"  Workflows active: {result[3]}")

# Distribution by confidence band
print(f"\nCONFIDENCE BAND DISTRIBUTION:")
cursor.execute('''
SELECT confidence_band, COUNT(*) as cnt
FROM phase1_metrics
GROUP BY confidence_band
ORDER BY confidence_band
''')

for band, count in cursor.fetchall():
    print(f"  {band}: {count}")

# Distribution by LLM call
print(f"\nLLM CALLED DISTRIBUTION:")
cursor.execute('''
SELECT llm_called, COUNT(*) as cnt
FROM phase1_metrics
GROUP BY llm_called
''')

for llm_flag, count in cursor.fetchall():
    status = 'YES' if llm_flag else 'NO' if llm_flag is not None else 'NULL'
    print(f"  {status}: {count}")

# Recent 10 records
print(f"\nLAST 10 RECORDS:")
print(f"{'ID':<4} {'Intent':<10} {'Band':<6} {'LLM':<4} {'Clarif':<7} {'Confirm':<8} {'Workflow':<9}")
print("-" * 70)

cursor.execute('''
SELECT 
  id, 
  intent_name, 
  confidence_band,
  llm_called,
  clarification_triggered,
  clarification_confirmed,
  workflow_active
FROM phase1_metrics
ORDER BY id DESC
LIMIT 10
''')

for row in cursor.fetchall():
    id_val, intent, band, llm, clarif, confirm, workflow = row
    llm_str = 'Y' if llm else 'N'
    clarif_str = 'Y' if clarif else 'N'
    confirm_str = 'Y' if confirm else 'N'
    workflow_str = 'Y' if workflow else 'N'
    print(f"{id_val:<4} {intent:<10} {band:<6} {llm_str:<4} {clarif_str:<7} {confirm_str:<8} {workflow_str:<9}")

conn.close()

print("\n" + "=" * 70)
print("END PASS 1")
