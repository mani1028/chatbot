#!/usr/bin/env python3
"""
ERROR CLEANUP VALIDATION

Send 1 request and check for remaining log errors/warnings
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
from database import db
import sqlite3

app = create_app()

print("ERROR CLEANUP VALIDATION")
print("=" * 80)

# Get site key
site_key = None
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()
cursor.execute("SELECT public_key FROM sites LIMIT 1")
result = cursor.fetchone()
if result:
    site_key = result[0]
conn.close()

print("\n[SENDING 1 TEST REQUEST]")
with app.test_client() as client:
    payload = {
        'message': 'Test message for error cleanup validation',
        'session_id': 'cleanup-test-001',
        'site_key': site_key,
        'page_url': 'http://localhost/test'
    }
    
    response = client.post('/api/chat', json=payload)
    print(f"HTTP Status: {response.status_code}")

print("\n[CHECK LOGS]")
print("Review output above for:")
print("  - 'unanswered_questions.site_id' errors (should be GONE)")
print("  - 'ChatLog creation failed' warnings (should be GONE)")
print("  - 'Rule error' with NoneType (should be GONE)")
print("  - 'Context analysis error' with NoneType (should be GONE)")
print("\nLogs should show:")
print("  - INFO: Request processing (no errors)")
print("  - DEBUG: Intent detection")
print("  - INFO: LLM callout")
print("  - INFO: Thread persisted")
print("\n" + "=" * 80)
