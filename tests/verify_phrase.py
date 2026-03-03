"""
Verify that the phrase was actually added to IntentPhrase table during PASS 4 Step 2
"""

from app import app
from database import db
from models.intent import Intent, IntentPhrase
from models.unknown_intent_log import UnknownIntentLog

with app.app_context():
    print("[CHECK 1] Verify phrase exists in IntentPhrase table")
    print("=" * 70)

    # Query for the phrase we added
    phrase_row = db.session.query(IntentPhrase).filter(
        IntentPhrase.phrase == "pricing insurance"
    ).first()

    if phrase_row:
        print(f"[OK] Found phrase in IntentPhrase:")
        print(f"  - Intent ID: {phrase_row.intent_id}")
        print(f"  - Phrase: {phrase_row.phrase}")
        print(f"  - Created: {phrase_row.created_at}")
    else:
        print("[ERROR] Phrase NOT found in IntentPhrase table!")
        print("\nAll phrases in table:")
        all_phrases = db.session.query(IntentPhrase).limit(20).all()
        for p in all_phrases:
            print(f"  - Intent {p.intent_id}: '{p.phrase}'")

    print("\n[CHECK 2] Verify Intent.phrases relationship loads correctly")
    print("=" * 70)

    # Get the pricing_general intent (ID 9)
    intent = db.session.query(Intent).filter(Intent.id == 9).first()

    if intent:
        print(f"[OK] Found intent: {intent.intent_name} (ID: {intent.id})")
        
        # Try to load phrases
        phrases = intent.phrases.all()
        print(f"[OK] Intent has {len(phrases)} phrases:")
        for phrase_obj in phrases:
            print(f"  - '{phrase_obj.phrase}'")
            
        # Check if our phrase is there
        has_our_phrase = any(p.phrase == "pricing insurance" for p in phrases)
        if has_our_phrase:
            print("\n[OK] 'pricing insurance' phrase IS in the intent!")
        else:
            print("\n[ERROR] 'pricing insurance' phrase NOT found in intent.phrases!")
    else:
        print("[ERROR] Intent ID 9 not found!")

    print("\n[CHECK 3] Verify unknown logs are marked resolved")
    print("=" * 70)

    unknown_logs = db.session.query(UnknownIntentLog).filter(
        UnknownIntentLog.message == "pricing insurance"
    ).all()

    print(f"[OK] Found {len(unknown_logs)} logs for 'pricing insurance':")
    for log in unknown_logs:
        print(f"  - ID: {log.id}, Resolved: {log.resolved}")

    resolved_count = sum(1 for log in unknown_logs if log.resolved)
    print(f"\n[STATUS] {resolved_count}/{len(unknown_logs)} marked as resolved")
