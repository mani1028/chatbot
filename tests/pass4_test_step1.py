#!/usr/bin/env python
"""
PASS 4 — Step 1: Trigger UNKNOWN intent
"""
import requests
import json
import time
from database import db, init_db
from app import create_app
from models import Site, ChatLog
from sqlalchemy import func

# Setup
app = create_app()

with app.app_context():
    # Get or create test site (use site_id=2 which has intents!)
    site = Site.query.filter(Site.id == 2).first()
    if not site:
        print("[ERROR] Site ID 2 not found!")
        sys.exit(1)
    
    print(f"[OK] Using site ID: {site.id} ({site.name})")
    
    site_key = site.public_key
    
print(f"\n[STEP 1] Sending unknown message: 'pricing insurance'")
print(f"Using site_key: {site_key}\n")

# Send message via HTTP
try:
    response = requests.post(
        'http://localhost:5000/api/chat',
        json={
            'site_key': site_key,
            'session_id': 'pass4-session-1',
            'message': 'pricing insurance'
        },
        timeout=5
    )
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}\n")
    
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"❌ HTTP request failed: {e}")
    exit(1)

# Wait a bit for database to process
time.sleep(1)

# Check database
print(f"\n[VERIFICATION] Checking database for UNKNOWN intent...")

with app.app_context():
    # Get most recent chat_log for this session
    log = ChatLog.query.filter_by(
        session_id='pass4-session-1'
    ).order_by(ChatLog.id.desc()).first()
    
    if log:
        print(f"[OK] Found chat_log entry:")
        print(f"  - ID: {log.id}")
        print(f"  - Message: {log.user_message}")
        print(f"  - Detected Intent: {log.detected_intent}")
        print(f"  - Confidence: {log.confidence}")
        print(f"  - Bot Response: {log.bot_response[:80] if log.bot_response else 'None'}...")
        
        if log.detected_intent == 'UNKNOWN':
            print(f"\n[PASS 1 OK] Intent correctly detected as UNKNOWN")
        else:
            print(f"\n[PASS 1 FAIL] Expected UNKNOWN, got {log.detected_intent}")
    else:
        print(f"[FAIL] No chat_log found for this session")
        exit(1)

print(f"\n[STEP 1 COMPLETE] Ready for Step 2: Map in Dashboard")
