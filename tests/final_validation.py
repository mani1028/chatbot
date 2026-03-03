#!/usr/bin/env python3
"""
Phase 1 Validation - Corrected test using actual return structure
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

print("="*70)
print("PHASE 1 VALIDATION - CLARIFICATION CONFIRMATION FIX")
print("="*70)

from app import app, db
from models import ConversationThread
from services.message_orchestrator import MessageOrchestrator

def test_1_confirmation():
    """Confirmation with 'yes' should skip detection"""
    print("\n[TEST 1] Confirmation Skip Detection")
    try:
        with app.app_context():
            app.config['TESTING'] = True
            orch = MessageOrchestrator()
            
            # Setup: thread with pending clarification
            thread = ConversationThread(
                site_id='t1', session_id='t1',
                pending_clarification='PAYMENT_INFO'
            )
            db.session.add(thread)
            db.session.commit()
            print("  [OK] Thread created with pending_clarification='PAYMENT_INFO'")
            
            # Send confirmation
            result = orch.process_message('t1', 't1', 'yes')
            
            # Check result
            assert result['intent_name'] == 'PAYMENT_INFO', f"Got {result['intent_name']}"
            assert result['intent_confidence'] == 1.0, f"Got {result['intent_confidence']}"
            print(f"  [OK] Confirmed: {result['intent_name']} @ {result['intent_confidence']}")
            
            # Check thread state
            thread = ConversationThread.query.filter_by(
                site_id='t1', session_id='t1'
            ).first()
            assert thread.pending_clarification is None, "pending should be cleared"
            print("  [OK] Cleared pending_clarification")
            
            print("[PASS] Confirmation works correctly\n")
            return True
    except Exception as e:
        print(f"[FAIL] {e}\n")
        return False

def test_2_denial():
    """Denial with 'no' should continue to detection"""
    print("[TEST 2] Denial Continue Detection")
    try:
        with app.app_context():
            app.config['TESTING'] = True
            orch = MessageOrchestrator()
            
            thread = ConversationThread(
                site_id='t2', session_id='t2',
                pending_clarification='PAYMENT_INFO'
            )
            db.session.add(thread)
            db.session.commit()
            print("  [OK] Thread created with pending_clarification='PAYMENT_INFO'")
            
            # Send denial
            result = orch.process_message('t2', 't2', 'no')
            
            # Should NOT confirm to PAYMENT_INFO
            assert result['intent_name'] != 'PAYMENT_INFO', f"Got {result['intent_name']}"
            print(f"  [OK] Did not confirm (got {result['intent_name']})")
            
            # pending should be cleared
            thread = ConversationThread.query.filter_by(
                site_id='t2', session_id='t2'
            ).first()
            assert thread.pending_clarification is None, "pending should be cleared"
            print("  [OK] Cleared pending_clarification")
            
            print("[PASS] Denial continues to detection\n")
            return True
    except Exception as e:
        print(f"[FAIL] {e}\n")
        return False

def test_3_tolerant():
    """Multiple confirmation variations"""
    print("[TEST 3] Tolerant Matching")
    variations = ["yes", "yeah", "y"]
    try:
        for i, var in enumerate(variations):
            with app.app_context():
                app.config['TESTING'] = True
                orch = MessageOrchestrator()
                
                sid = f't3_{i}'
                thread = ConversationThread(
                    site_id=sid, session_id=sid,
                    pending_clarification='PAYMENT_INFO'
                )
                db.session.add(thread)
                db.session.commit()
                
                result = orch.process_message(sid, sid, var)
                assert result['intent_confidence'] == 1.0, f"'{var}' -> {result['intent_confidence']}"
                print(f"  [OK] '{var}' confirmed")
        
        print("[PASS] All variations work\n")
        return True
    except Exception as e:
        print(f"[FAIL] {e}\n")
        return False

# Run tests
results = [
    ("Test 1: Confirmation skip detection", test_1_confirmation()),
    ("Test 2: Denial continue detection", test_2_denial()),
    ("Test 3: Tolerant matching", test_3_tolerant()),
]

# Summary
print("="*70)
print("RESULTS")
print("="*70)
for name, passed in results:
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}")

all_passed = all(r[1] for r in results)
print("="*70)
if all_passed:
    print("\n[SUCCESS] All tests passed!")
    print("The clarification confirmation fix is working correctly.")
    sys.exit(0)
else:
    print("\n[ERROR] Some tests failed.")
    sys.exit(1)
