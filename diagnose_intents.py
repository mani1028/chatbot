#!/usr/bin/env python3
"""Diagnose intent configuration issues"""
import sys
sys.path.insert(0, '/c/Users/HP/OneDrive/Desktop/chatbot')

from app import app
from models.intent import Intent
from models.site import Site

with app.app_context():
    # Check test site
    site = Site.query.filter_by(site_key="kernel_test_key").first()
    print(f"\n{'='*60}")
    print(f"TEST SITE LOOKUP")
    print(f"{'='*60}")
    if site:
        print(f"✓ Site found: {site.name}")
        print(f"  ID: {site.id}")
        print(f"  Key: {site.site_key}")
    else:
        print(f"✗ Site NOT FOUND - kernel_test_key doesn't exist!")
        sys.exit(1)
    
    site_id = site.id
    print()
    
    # Check business_hours intent
    print(f"{'='*60}")
    print(f"BUSINESS_HOURS INTENT LOOKUP")
    print(f"{'='*60}")
    bh = Intent.query.filter_by(intent_name="business_hours").first()
    if bh:
        print(f"✓ Intent found: business_hours")
        print(f"  Site ID: {bh.site_id} (0=global, {site_id}=this site)")
        print(f"  Type: {bh.intent_type}")
        phrase_count = len(bh.phrases or [])
        print(f"  Phrases: {phrase_count}")
        if bh.phrases:
            print(f"\n  First 5 phrases:")
            for p in bh.phrases[:5]:
                print(f"    - '{p.phrase}'")
        
        # Check if visible to this site
        if bh.site_id == 0:
            print(f"\n  ✓ GLOBAL - visible to all sites")
        elif bh.site_id == site_id:
            print(f"\n  ✓ SITE-SCOPED - visible to this site only")
        else:
            print(f"\n  ✗ PROBLEM - belongs to site {bh.site_id}, not accessible to site {site_id}")
    else:
        print(f"✗ Intent NOT FOUND - business_hours doesn't exist!")
    
    print()
    print(f"{'='*60}")
    print(f"ALL INTENTS FOR THIS SITE")
    print(f"{'='*60}")
    intents = Intent.query.filter((Intent.site_id == 0) | (Intent.site_id == site_id)).all()
    print(f"Total intents (global + site-scoped): {len(intents)}\n")
    
    for intent in intents:
        phrase_count = len(intent.phrases or [])
        scope = "GLOBAL" if intent.site_id == 0 else "SITE"
        print(f"  {intent.intent_name:25} | {scope:6} | type={intent.intent_type:10} | #{phrase_count:2}")
    
    print()
    print(f"{'='*60}")
    print(f"DIAGNOSIS")
    print(f"{'='*60}")
    if bh:
        if bh.site_id in (0, site_id):
            print("✓ Intent is accessible from this site")
            if bh.phrases:
                print("✓ Intent has phrase patterns defined")
                print("\n→ If still returning UNKNOWN:")
                print("  1. Check if pattern matching threshold is too high")
                print("  2. Verify message tokenization")
                print("  3. Check fuzzy matching tolerance")
                print("  4. Run intent_handle_message with debug logging")
            else:
                print("✗ Intent has NO PHRASES - that's the problem!")
        else:
            print(f"✗ Intent belongs to site {bh.site_id}, not accessible!")
    else:
        print("✗ business_hours intent doesn't exist - create it or import it")
