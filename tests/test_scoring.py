#!/usr/bin/env python3
"""Test intent detection scoring directly"""
import sys
import time
time.sleep(2)  # Let Flask/imports settle

from app import app
with app.app_context():
    from core.intent_engine import detect_intent
    from models.intent import Intent
    
    # Test message
    msg = "What are your hours?"
    site_id = 3  # test site
    
    print(f"\n{'='*70}")
    print(f"INTENT SCORING TEST")
    print(f"{'='*70}")
    print(f"Message: '{msg}'")
    print(f"Site ID: {site_id}")
    
    # Get the actual business_hours intent from DB
    bh_intent = Intent.query.filter_by(intent_name="business_hours").first()
    print(f"\nbusiness_hours intent in DB:")
    if bh_intent:
        print(f"  ✓ Found, site_id={bh_intent.site_id}")
        print(f"  Phrases ({len(bh_intent.phrases or [])}): {[p.phrase for p in (bh_intent.phrases or [])][:5]}")
        print(f"  confidence_threshold: {bh_intent.confidence_threshold}")
    else:
        print(f"  ✗ Not found!")
    
    # Run detection
    print(f"\nRunning detect_intent()...")
    result = detect_intent(msg, site_id)
    
    print(f"\nResult:")
    print(f"  intent_name: {result.get('intent_name')}")
    print(f"  confidence: {result.get('confidence')}")
    print(f"  response: {result.get('response', '')[:60]}...")
    
    # Explanation
    print(f"\n{'='*70}")
    print(f"INTERPRETATION")
    print(f"{'='*70}")
    if result.get('intent_name') == 'business_hours':
        print("✓ Intent correctly detected as 'business_hours'")
    elif result.get('intent_name') == 'UNKNOWN':
        conf = result.get('confidence', 0)
        if conf < 0.3:
            print(f"✗ PROBLEM: confidence {conf} < 0.3 (LLM fallback threshold)")
            print(f"  The pattern matching algorithm is scoring too low")
            print(f"  This might be due to:")
            print(f"    - Fuzzy threshold (80) too high")
            print(f"    - Phrase missing from DB phrases")
            print(f"    - Site-scoped vs global mismatch")
        elif conf < 0.65:
            print(f"✗ CAUTION: confidence {conf} < 0.65 (suggestion threshold)")
            print(f"  The intent scored above LLM trigger but below suggestion")
            print(f"  Will suggest intent rather than stating it")
        else:
            print(f"? Intent returned UNKNOWN despite confidence {conf} >= 0.65")
    
    print()
