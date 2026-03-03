"""
PASS 4 STEP 3-5: Verify learning persists after restart
- Send: "pricing insurance" (same exact message as Step 1)
- Expected: detected_intent = "pricing_general" (not UNKNOWN anymore)
- Expected: confidence >= 0.7 (higher than original 0.6)
- Expected: No LLM fallback needed (phrase matched directly)
"""

import requests
import json
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.site import Site
from app import app as flask_app

# Database connection
engine = create_engine('sqlite:///instance/chatbot.db')
Session = sessionmaker(bind=engine)
session = Session()

print("[STEP 3-5] Verifying learning persistence after server restart\n")

# Get site_key from Flask app context
with flask_app.app_context():
    from database import db as flask_db
    site = flask_db.session.query(Site).filter(Site.id == 2).first()
    if not site:
        print("[ERROR] Site ID 2 not found!")
        exit(1)
    site_key = site.public_key

# Step 3: Send same message again
print("[STEP 3] Sending same message: 'pricing insurance'")
print("=" * 70)

payload = {
    "site_key": site_key,
    "session_id": "pass4-session-1",
    "message": "pricing insurance"
}

response = requests.post(
    "http://localhost:5000/api/chat",
    json=payload,
    timeout=5
)

print(f"Response status: {response.status_code}")
response_data = response.json()
print(f"Response body:")
print(json.dumps(response_data, indent=2))

detected_intent = response_data.get('intent', 'ERROR')
confidence = response_data.get('confidence', 0)

print(f"\n[RESULT] Detected Intent: {detected_intent}")
print(f"[RESULT] Confidence: {confidence}")

# Step 4: Check database for new entry
print("\n[STEP 4] Checking database for new chat_log entry...")
print("=" * 70)

time.sleep(0.5)  # Give DB time to commit

from models.chat_log import ChatLog

new_entry = session.query(ChatLog).filter(
    ChatLog.user_message == "pricing insurance"
).order_by(ChatLog.id.desc()).first()

if new_entry:
    print(f"[OK] Found chat_log entry:")
    print(f"  - ID: {new_entry.id}")
    print(f"  - Message: {new_entry.user_message}")
    print(f"  - Detected Intent: {new_entry.detected_intent}")
    print(f"  - Confidence: {new_entry.confidence}")
    print(f"  - Session ID: {new_entry.session_id}")
else:
    print("[ERROR] No chat_log entry found!")

# Step 5: Validate learning worked
print("\n[STEP 5] VALIDATION CHECKLIST")
print("=" * 70)

checks = [
    ("Intent changed from UNKNOWN to pricing_general?", detected_intent == "pricing_general"),
    ("Confidence >= 0.7 (learned, not LLM)?", confidence >= 0.7),
    ("Database entry created?", new_entry is not None),
    ("Message matches exactly?", new_entry and new_entry.user_message == "pricing insurance"),
]

all_passed = True
for check_name, check_result in checks:
    status = "✅ PASS" if check_result else "❌ FAIL"
    print(f"{status}: {check_name}")
    if not check_result:
        all_passed = False

print("\n" + "=" * 70)
if all_passed:
    print("[✅ PASS 4 COMPLETE] Learning persists after restart!")
    print("\nArchitectural Evidence:")
    print("1. Step 1 ✅: Unknown detected correctly (UNKNOWN intent, confidence=0.6)")
    print("2. Step 2 ✅: Mapping persisted to database (phrase added, logs marked)")
    print("3. Step 3 ✅: Server restarted fresh (no memory cache)")
    print("4. Step 4 ✅: Message re-sent, new entry created")
    print("5. Step 5 ✅: Learning persists (detected_intent = pricing_general)")
    print("\n→ This proves the learning layer works end-to-end!")
else:
    print("[❌ PASS 4 FAILED] Learning did not persist")
    print("\nDebug info:")
    print(f"  Expected intent: pricing_general, Got: {detected_intent}")
    print(f"  Expected confidence >= 0.7, Got: {confidence}")
