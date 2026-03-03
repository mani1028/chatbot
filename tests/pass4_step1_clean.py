#!/usr/bin/env python
"""
PASS 4 — Step 1: Trigger UNKNOWN intent  
"""
import sys
print("[INIT] Starting Step 1", flush=True)

import requests
import json
print("[INIT] Imported requests/json", flush=True)

from database import db, init_db
from app import create_app
from models import Site, ChatLog
from sqlalchemy import func
print("[INIT] Imported app/models", flush=True)

# Setup
app = create_app()
print("[INIT] Created Flask app", flush=True)

with app.app_context():
    print("[INIT] Inside app context", flush=True)
    
    # Get or create test site (use site_id=2 which has intents!)
    site = Site.query.filter(Site.id == 2).first()
    if not site:
        print("[ERROR] Site ID 2 not found!", flush=True)
        sys.exit(1)
    
    print(f"[OK] Using site ID: {site.id} ({site.name})", flush=True)
    
    site_key = site.public_key
    
print(f"\n[STEP 1] Sending unknown message: 'pricing insurance'")
print(f"Using site_key: {site_key}\n")

# Send message via HTTP
try:
    response = requests.post(
        "http://localhost:5000/api/chat",
        json={
            "site_key": site_key,
            "session_id": "pass4-session-1",
            "message": "pricing insurance"
        },
        timeout=5
    )
    
    print(f"Response status: {response.status_code}")
    
    response_data = response.json()
    print(f"Response intent: {response_data.get('intent')}")
    print(f"Response confidence: {response_data.get('confidence')}")
    
except Exception as e:
    print(f"[ERROR] Failed to send message: {e}")
    sys.exit(1)

# Verify in database
with app.app_context():
    entry = ChatLog.query.filter_by(session_id="pass4-session-1").order_by(ChatLog.id.desc()).first()
    if entry:
        print(f"\n[VERIFICATION] Found chat_log entry:")
        print(f"  - ID: {entry.id}")
        print(f"  - Message: {entry.user_message}")
        print(f"  - Detected Intent: {entry.detected_intent}")
        print(f"  - Confidence: {entry.confidence}")
    else:
        print("[ERROR] No chat_log entry found!")

print("\n[PASS 1 OK]")
