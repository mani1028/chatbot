#!/usr/bin/env python3
"""
Direct endpoint test - no subprocess, just test the app locally
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app
import json

app = create_app()

print("Testing endpoint locally...")
print("=" * 60)

with app.test_client() as client:
    # Get valid site_key
    import sqlite3
    conn = sqlite3.connect('instance/chatbot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT public_key FROM sites LIMIT 1")
    site_key = cursor.fetchone()[0]
    conn.close()
    
    # Test payload
    payload = {
        'message': 'Test message',
        'session_id': 'test-session-1',
        'site_key': site_key,
        'page_url': 'http://localhost/test'
    }
    
    print(f"Site key: {site_key}")
    print(f"Endpoint: POST /api/chat")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nResponse:")
    
    response = client.post('/api/chat', json=payload)
    print(f"  Status: {response.status_code}")
    print(f"  Content-Type: {response.content_type}")
    
    try:
        data = response.get_json()
        print(f"  Response: {json.dumps(data, indent=2)[:200]}")
    except:
        print(f"  Response body: {response.data[:200]}")

print("\n" + "=" * 60)
print("Local test complete")
