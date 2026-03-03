#!/usr/bin/env python3
"""
Phase 1 Validation Test - Direct test of clarification confirmation logic
Bypasses intent detection complexity to focus on the core fix:
Ensuring clarification confirmation works correctly and doesn't get overwritten
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_clarification_confirmation_core():
    """
    Core Validation Test:
    - Set pending_clarification
    - Send "yes" confirmation
    - Verify: confirmation creates 1.0 confidence intent, clears pending, skips detection
    """
    print("\n" + "="*70)
    print("CORE FIX VALIDATION: Clarification Confirmation Logic")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        app.config['TESTING'] = True
        with app.app_context():
            orchestrator = MessageOrchestrator()
            
            # Setup
            site_id = 'test_site'
            session_id = 'test_confirm'
            
            # STEP 1: Manually set pending_clarification (simulating mid-session)
            print("\nSTEP 1: Create thread with pending_clarification")
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                pending_clarification='PAYMENT_INFO',  # Waiting for: "Did you mean PAYMENT_INFO?"
                pending_reply="Did you mean 'PAYMENT_INFO'?"
            )
            db.session.add(thread)
            db.session.commit()
            print(f"  [OK] pending_clarification = {thread.pending_clarification}")
            print(f"  [OK] pending_reply = {thread.pending_reply}")
            
            # STEP 2: Send confirmation "yes"
            print("\nSTEP 2: User sends 'yes' confirmation")
            result = orchestrator.process_message(site_id, session_id, "yes")
            
            # Reload thread to check state
            thread = ConversationThread.query.filter_by(
                site_id=site_id,
                session_id=session_id
            ).first()
            
            print(f"  Detected intent: {result.get('intent', {}).get('name', 'UNKNOWN')}")
            print(f"  Confidence: {result.get('intent', {}).get('confidence', 0):.2f}")
            print(f"  Pending clarification after: {thread.pending_clarification}")
            
            # STEP 3: Verify the fix
            intent_name = result.get('intent', {}).get('name')
            confidence = result.get('intent', {}).get('confidence', 0)
            
            print("\n[ASSERTIONS]")
            assert intent_name == 'PAYMENT_INFO', f"Should confirm to PAYMENT_INFO, got {intent_name}"
            print(f"  ✓ Confirmed intent is PAYMENT_INFO")
            
            assert confidence == 1.0, f"Should have confidence 1.0, got {confidence}"
            print(f"  ✓ Confidence is 1.0 (confirmed)")
            
            assert thread.pending_clarification is None, f"Should clear pending, got {thread.pending_clarification}"
            print(f"  ✓ Cleared pending_clarification")
            
            # Check execution trace
            trace = thread.execution_trace
            assert any('clarification_confirmed' in str(e) for e in trace[-2:]), "Should log confirmation"
            print(f"  ✓ Logged 'clarification_confirmed' in trace")
            
            assert 'intent_detected' not in str(trace[-2:]), "Should NOT re-detect after confirmation"
            print(f"  ✓ Did NOT re-run intent detection")
            
            print("\n✅ PASSED: Confirmation bypasses detection correctly")
            return True
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_clarification_denial_continues_detection():
    """
    Denial test:
    - Set pending_clarification
    - Send "no" denial
    - Verify: clears pending, continues to detection
    """
    print("\n" + "="*70)
    print("DENIAL VALIDATION: Denial should continue to detection")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        app.config['TESTING'] = True
        with app.app_context():
            orchestrator = MessageOrchestrator()
            
            # Setup
            site_id = 'test_site'
            session_id = 'test_denial'
            
            # STEP 1: Set pending_clarification
            print("\nSTEP 1: Create thread with pending_clarification")
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                pending_clarification='PAYMENT_INFO',
                pending_reply="Did you mean 'PAYMENT_INFO'?"
            )
            db.session.add(thread)
            db.session.commit()
            print(f"  ✓ pending_clarification = {thread.pending_clarification}")
            
            # STEP 2: Send denial "no"
            print("\nSTEP 2: User sends 'no' denial")
            result = orchestrator.process_message(site_id, session_id, "no")
            
            # Reload thread
            thread = ConversationThread.query.filter_by(
                site_id=site_id,
                session_id=session_id
            ).first()
            
            print(f"  Detected intent: {result.get('intent', {}).get('name', 'UNKNOWN')}")
            print(f"  Confidence: {result.get('intent', {}).get('confidence', 0):.2f}")
            print(f"  Pending clarification after: {thread.pending_clarification}")
            
            # STEP 3: Verify the denial
            print("\n[ASSERTIONS]")
            assert thread.pending_clarification is None, "Should clear pending after denial"
            print(f"  ✓ Cleared pending_clarification after denial")
            
            # Check that 'no' was run through detection (not confirmed as PAYMENT_INFO)
            intent_name = result.get('intent', {}).get('name')
            assert intent_name != 'PAYMENT_INFO', f"Should NOT be PAYMENT_INFO after denial, got {intent_name}"
            print(f"  ✓ Did NOT confirm to PAYMENT_INFO (got {intent_name} instead)")
            
            trace = thread.execution_trace
            assert any('clarification_denied' in str(e) for e in trace[-3:]), "Should log denial"
            print(f"  ✓ Logged 'clarification_denied' in trace")
            
            print("\n✅ PASSED: Denial continues to detection correctly")
            return True
            
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tolerant_confirmation_variations():
    """
    Tolerant matching test:
    - Test "yes sure", "yeah", "y" variations
    - All should confirm
    """
    print("\n" + "="*70)
    print("TOLERANT MATCHING: Multiple confirmation variations")
    print("="*70)
    
    from app import app, db
    from models import ConversationThread
    from services.message_orchestrator import MessageOrchestrator
    
    variations = ["yes", "yeah", "y", "yes sure", "yeah absolutely", "yes please"]
    
    try:
        app.config['TESTING'] = True
        
        for i, variation in enumerate(variations):
            print(f"\n  Variation {i+1}: '{variation}'")
            with app.app_context():
                orchestrator = MessageOrchestrator()
                site_id = f'test_site_{i}'
                session_id = f'test_tolerant_{i}'
                
                # Set pending
                thread = ConversationThread(
                    site_id=site_id,
                    session_id=session_id,
                    pending_clarification='PAYMENT_INFO'
                )
                db.session.add(thread)
                db.session.commit()
                
                # Send confirmation
                result = orchestrator.process_message(site_id, session_id, variation)
                
                # Reload and check
                thread = ConversationThread.query.filter_by(
                    site_id=site_id,
                    session_id=session_id
                ).first()
                
                confidence = result.get('intent', {}).get('confidence', 0)
                if confidence == 1.0:
                    print(f"    ✓ Confirmed (confidence={confidence})")
                else:
                    print(f"    ✗ NOT confirmed (confidence={confidence})")
                    raise AssertionError(f"'{variation}' should confirm but got confidence {confidence}")
        
        print("\n✅ PASSED: All variations confirm correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("PHASE 1 - CRITICAL FIX VALIDATION")
    print("Direct test of clarification confirmation logic")
    print("="*70)
    
    results = []
    
    try:
        results.append(("Core fix: Confirmation bypasses detection", test_clarification_confirmation_core()))
        results.append(("Denial: Continues to detection", test_clarification_denial_continues_detection()))
        results.append(("Tolerant matching: Multiple variations", test_tolerant_confirmation_variations()))
    except Exception as e:
        print(f"\n⚠️  Critical error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("="*70)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED")
        print("Clarification confirmation logic is working correctly!")
        print("Ready for production deployment.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("Review the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
