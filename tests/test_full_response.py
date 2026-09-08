#!/usr/bin/env python
"""Test full response pipeline for apollo site."""

from app import app, db
from services.chat_service import process_message

with app.app_context():
    print("=" * 70)
    print("FULL RESPONSE PIPELINE TEST")
    print("=" * 70)
    
    test_messages = [
        "hello",
        "timings",
        "help",
    ]
    
    for message in test_messages:
        print(f"\n[Testing message: '{message}']")
        
        # Call the process_message function that the widget uses
        response = process_message(
            site_id=2,  # apollo
            user_message=message,
            session_id="test-session"
        )
        
        print(f"  Intent: {response.intent_name}")
        print(f"  Confidence: {response.confidence}")
        print(f"  Reply: {response.reply[:100] if response.reply else 'EMPTY'}")
        print(f"  Handoff: {response.handoff}")
        print(f"  Lead Capture: {response.lead_capture}")
    
    print("\n" + "=" * 70)
