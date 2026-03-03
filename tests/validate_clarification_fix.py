#!/usr/bin/env python3
"""
Phase 1 Validation - Direct test of clarification confirmation logic
Tests that confirmation works correctly without depending on intent detection
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_clarification_confirmation():
    """Test that confirmation creates 1.0 confidence intent and skips detection"""
    print("\n" + "="*70)
    print("TEST 1: Denial bypasses detection")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        app.config['TESTING'] = True
        with app.app_context():
            orchestrator = MessageOrchestrator()
            
            # SETUP: Thread with pending_clarification
            site_id = 'test_site'
            session_id = 'test_confirm'
            
            print("\nStep 1: Create thread with pending_clarification = 'PAYMENT_INFO'")
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                pending_clarification='PAYMENT_INFO'
            )
            db.session.add(thread)
            db.session.commit()
            print(f"  [OK] Thread created")
            
            # TEST: Send "yes" confirmation
            print("\nStep 2: User sends confirmation 'yes'")
            result = orchestrator.process_message(site_id, session_id, "yes")
            
            # Reload and verify
            thread = ConversationThread.query.filter_by(
                site_id=site_id,
                session_id=session_id
            ).first()
            
            intent_name = result.get('intent', {}).get('name')
            confidence = result.get('intent', {}).get('confidence', 0)
            
            print(f"  Intent: {intent_name}, Confidence: {confidence}")
            print(f"  Pending clarification: {thread.pending_clarification}")
            
            # VERIFY
            assert intent_name == 'PAYMENT_INFO', f"Expected PAYMENT_INFO, got {intent_name}"
            print("[OK] Confirmed to PAYMENT_INFO")
            
            assert confidence == 1.0, f"Expected confidence 1.0, got {confidence}"
            print("[OK] Confidence = 1.0")
            
            assert thread.pending_clarification is None, "Should clear pending"
            print("[OK] Cleared pending_clarification")
            
            assert not any('intent_detected' in str(e) for e in thread.execution_trace[-2:]), "Should NOT detect"
            print("[OK] Skipped intent detection")
            
            print("\n[PASS] Confirmation works correctly")
            return True
            
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_clarification_denial():
    """Test that denial clears pending and continues to detection"""
    print("\n" + "="*70)
    print("TEST 2: Denial continues to detection")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        app.config['TESTING'] = True
        with app.app_context():
            orchestrator = MessageOrchestrator()
            
            site_id = 'test_site'
            session_id = 'test_denial'
            
            print("\nStep 1: Create thread with pending_clarification = 'PAYMENT_INFO'")
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                pending_clarification='PAYMENT_INFO'
            )
            db.session.add(thread)
            db.session.commit()
            print("[OK] Thread created")
            
            # TEST: Send "no" denial
            print("\nStep 2: User sends denial 'no'")
            result = orchestrator.process_message(site_id, session_id, "no")
            
            # Reload and verify
            thread = ConversationThread.query.filter_by(
                site_id=site_id,
                session_id=session_id
            ).first()
            
            intent_name = result.get('intent', {}).get('name')
            
            print(f"  Intent: {intent_name}")
            print(f"  Pending: {thread.pending_clarification}")
            
            # VERIFY
            assert thread.pending_clarification is None, "Should clear pending after denial"
            print("[OK] Cleared pending_clarification")
            
            assert intent_name != 'PAYMENT_INFO', "Should NOT confirm after denial"
            print(f"[OK] Did not confirm (got {intent_name})")
            
            assert any('clarification_denied' in str(e) for e in thread.execution_trace[-3:]), "Should log denial"
            print("[OK] Logged clarification_denied")
            
            print("\n[PASS] Denial works correctly")
            return True
            
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tolerant_matching():
    """Test tolerant confirmation matching"""
    print("\n" + "="*70)
    print("TEST 3: Tolerant confirmation matching")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    variations = ["yes", "yeah", "y", "yes sure", "yeah absolutely"]
    
    try:
        app.config['TESTING'] = True
        
        for i, variation in enumerate(variations):
            with app.app_context():
                orchestrator = MessageOrchestrator()
                site_id = f'test_site_{i}'
                session_id = f'test_tol_{i}'
                
                thread = ConversationThread(
                    site_id=site_id,
                    session_id=session_id,
                    pending_clarification='PAYMENT_INFO'
                )
                db.session.add(thread)
                db.session.commit()
                
                result = orchestrator.process_message(site_id, session_id, variation)
                confidence = result.get('intent', {}).get('confidence', 0)
                
                if confidence == 1.0:
                    print(f"  [{i+1}] '{variation}' -> Confirmed")
                else:
                    raise AssertionError(f"'{variation}' should confirm but got {confidence}")
        
        print("\n[PASS] All variations confirmed")
        return True
        
    except Exception as e:
        print(f"\n[FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("PHASE 1 - CLARIFICATION FIX VALIDATION")
    print("Testing core confirmation logic directly")
    print("="*70)
    
    results = [
        ("TEST 1: Confirmation logic", test_clarification_confirmation()),
        ("TEST 2: Denial logic", test_clarification_denial()),
        ("TEST 3: Tolerant matching", test_tolerant_matching()),
    ]
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("="*70)
    if all_passed:
        print("[RESULT] ALL TESTS PASSED - Fix is working correctly")
        return 0
    else:
        print("[RESULT] SOME TESTS FAILED - See above for details")
        return 1

if __name__ == '__main__':
    sys.exit(main())
