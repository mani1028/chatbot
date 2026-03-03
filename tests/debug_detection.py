"""
Debug intent detection to see why phrases aren't matching
"""

import sys
sys.stdout.flush()  # Force flush

from app import app
from database import db
from core.intent_engine import IntentEngine
from models.intent import Intent
from sqlalchemy import or_

with app.app_context():
    print("[DEBUG] Starting intent detection test", flush=True)
    
    print("[DEBUG] Checking database connection", flush=True)
    try:
        # Test basic query
        all_intents = Intent.query.all()
        print(f"[OK] Total intents in database: {len(all_intents)}", flush=True)
    except Exception as e:
        print(f"[ERROR] Can't query intents: {e}", flush=True)
        sys.exit(1)
    
    print("[DEBUG] Testing intent detection for: 'pricing insurance'", flush=True)
    print("=" * 70, flush=True)
    
    engine = IntentEngine()
    
    # Test directly
    result = engine.detect_intent("pricing insurance", site_id=8)
    
    print(f"\nDetection result:", flush=True)
    print(f"  Intent: {result.get('intent')}", flush=True)
    print(f"  Confidence: {result.get('confidence')}", flush=True)
    print(f"  Score: {result.get('score', 'N/A')}", flush=True)
    
    # Now debug: load intents manually with correct query
    print(f"\n[DEBUG] Manual intent loading with or_():", flush=True)
    print("=" * 70, flush=True)
    
    intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == 8)).all()
    
    print(f"Found {len(intents)} intents for site_id 0 or 8", flush=True)
    
    # Find intent ID 9 (pricing_general)
    pricing_intent = next((i for i in intents if i.id == 9), None)
    
    if pricing_intent:
        print(f"\n[OK] Found pricing intent: {pricing_intent.intent_name} (ID: {pricing_intent.id})", flush=True)
        
        # Check phrases
        phrases = pricing_intent.phrases.all()
        print(f"[OK] Intent has {len(phrases)} phrases:", flush=True)
        
        pricing_insurance_phrase = None
        for phrase in phrases[:10]:  # Show first 10
            print(f"  - '{phrase.phrase}'", flush=True)
            if phrase.phrase == "pricing insurance":
                pricing_insurance_phrase = phrase
        
        if pricing_insurance_phrase:
            print(f"\n[FOUND] 'pricing insurance' phrase exists in intent!", flush=True)
        else:
            print(f"\n[ERROR] 'pricing insurance' phrase NOT in loaded phrases!", flush=True)
    else:
        print(f"\n[ERROR] Intent ID 9 not found in loaded intents!", flush=True)
        
    print("\n[DEBUG] What intents were loaded?", flush=True)
    for intent in intents[:10]:
        print(f"  - {intent.intent_name} (site_id: {intent.site_id})", flush=True)

