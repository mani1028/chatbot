#!/usr/bin/env python3
"""
Debug test - send one message and trace metrics insertion
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
from models.phase1_metrics import Phase1Metrics
import sqlite3

app = create_app()

print("PRE-REQUEST STATE")
print("=" * 70)

# Check initial metrics count
with app.app_context():
    initial_count = db.session.query(Phase1Metrics).count()
    print(f"Initial metrics records: {initial_count}")

print("\nSENDING REQUEST...")
print("=" * 70)

# Send one request
with app.test_client() as client:
    import sqlite3
    conn = sqlite3.connect('instance/chatbot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT public_key FROM sites LIMIT 1")
    site_key = cursor.fetchone()[0]
    conn.close()
    
    payload = {
        'message': 'Hello',
        'session_id': 'debug-test-1',
        'site_key': site_key,
        'page_url': 'http://localhost/test'
    }
    
    print(f"Payload: {payload}")
    response = client.post('/api/chat', json=payload)
    print(f"Response status: {response.status_code}")

print("\nPOST-REQUEST STATE")
print("=" * 70)

# Check metrics count after request
with app.app_context():
    final_count = db.session.query(Phase1Metrics).count()
    inserted = final_count - initial_count
    print(f"Final metrics records: {final_count}")
    print(f"Inserted: {inserted}")
    
    if inserted > 0:
        # Show the inserted record
        metrics = db.session.query(Phase1Metrics).order_by(Phase1Metrics.id.desc()).first()
        print(f"\nLatest metrics record:")
        print(f"  ID: {metrics.id}")
        print(f"  Intent: {metrics.intent_name}")
        print(f"  Confidence: {metrics.intent_confidence}")
        print(f"  Band: {metrics.confidence_band}")
        print(f"  LLM called: {metrics.llm_called}")
        print(f"  Clarification: {metrics.clarification_triggered}")
        print(f"  Workflow: {metrics.workflow_active}")

print("\nDONE")
