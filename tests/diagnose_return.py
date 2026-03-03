#!/usr/bin/env python3
"""Quick diagnostic to see what process_message returns"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import ConversationThread
from services.message_orchestrator import MessageOrchestrator

with app.app_context():
    app.config['TESTING'] = True
    
    orchestrator = MessageOrchestrator()
    thread = ConversationThread(
        site_id='test',
        session_id='test',
        pending_clarification='PAYMENT_INFO'
    )
    db.session.add(thread)
    db.session.commit()
    
    result = orchestrator.process_message('test', 'test', 'yes')
    
    print("\n=== RETURN VALUE STRUCTURE ===")
    print(f"Type: {type(result)}")
    print(f"Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
    print(f"\nFull result:")
    import json
    print(json.dumps(result, default=str, indent=2))
