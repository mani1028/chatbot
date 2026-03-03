#!/usr/bin/env python3
"""
Phase 1 Validation Test - Test 3 critical scenarios
Validates the clarification confirmation fix
"""
import sys
import os
import json
from datetime import datetime

# Suppress heavy imports
os.environ['TRANSFORMERS_CACHE'] = '/tmp/transformers'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

sys.path.insert(0, os.path.dirname(__file__))

def setup_test_context():
    """Initialize minimal context without loading heavy models"""
    from app import app, db
    from models import ConversationThread
    
    app.config['TESTING'] = True
    context = app.app_context()
    context.push()
    return app, db, context, ConversationThread

def test_scenario_1_normal_clarification():
    """Test: User receives clarification, confirms with 'yes'"""
    print("\n" + "="*70)
    print("TEST 1: Normal Clarification → 'yes'")
    print("="*70)
    
    app, db, context, ConversationThread = setup_test_context()
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        orchestrator = MessageOrchestrator()
        
        # Step 1: Setup IDs (no need to create thread manually)
        site_id = 'test_site'
        session_id = 'test_session_1'
        print(f"✓ Setup site_id={site_id}, session_id={session_id}")
        
        # Step 2: Send ambiguous message "fees"
        print("\n[USER] 'fees'")
        result = orchestrator.process_message(site_id, session_id, "fees")
        
        # Get the thread to check state
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result.get('intent', {}).get('name', 'unknown')} (confidence: {result.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        print(f"  Bot reply: {thread.pending_reply}")
        print(f"  Trace: {thread.execution_trace[-3:]}")
        
        # Verify we entered clarification band
        assert thread.pending_clarification is not None, "Should have pending_clarification"
        assert 'clarification_band_triggered' in thread.execution_trace, "Should trigger clarification band"
        print("  ✓ Correctly entered clarification band")
        
        # Step 3: Confirm with "yes"
        print("\n[USER] 'yes'")
        result2 = orchestrator.process_message(site_id, session_id, "yes")
        
        # Reload thread
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result2.get('intent', {}).get('name', 'unknown')} (confidence: {result2.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        print(f"  Trace: {thread.execution_trace[-3:]}")
        
        # Verify confirmation worked
        assert result2.get('intent', {}).get('confidence', 0) == 1.0, "Confirmed intent should have confidence 1.0"
        assert thread.pending_clarification is None, "Should clear pending_clarification"
        assert any('clarification_confirmed' in str(entry) for entry in thread.execution_trace[-2:]), "Should log confirmation"
        print("  ✓ Correctly confirmed clarification")
        
        print("\n✅ PASSED: Normal clarification → yes")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scenario_2_tolerant_confirmation():
    """Test: User confirms with 'yes please' (not exact 'yes')"""
    print("\n" + "="*70)
    print("TEST 2: Tolerant Confirmation → 'yes please'")
    print("="*70)
    
    app, db, context, ConversationThread = setup_test_context()
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        orchestrator = MessageOrchestrator()
        
        # Step 1: Setup IDs
        site_id = 'test_site'
        session_id = 'test_session_2'
        print(f"✓ Setup site_id={site_id}, session_id={session_id}")
        
        # Step 2: Send ambiguous message
        print("\n[USER] 'fees'")
        result = orchestrator.process_message(site_id, session_id, "fees")
        
        # Get thread
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result.get('intent', {}).get('name', 'unknown')} (confidence: {result.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        assert thread.pending_clarification is not None, "Should have pending_clarification"
        print("  ✓ Entered clarification band")
        
        # Step 3: Confirm with "yes please" (tolerant matching)
        print("\n[USER] 'yes please'")
        result2 = orchestrator.process_message(site_id, session_id, "yes please")
        
        # Reload thread
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result2.get('intent', {}).get('name', 'unknown')} (confidence: {result2.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        print(f"  Trace: {thread.execution_trace[-3:]}")
        
        # Verify tolerant matching worked
        assert result2.get('intent', {}).get('confidence', 0) == 1.0, "Confirmed intent should have confidence 1.0"
        assert thread.pending_clarification is None, "Should clear pending_clarification"
        assert any('clarification_confirmed' in str(entry) for entry in thread.execution_trace[-2:]), "Should log confirmation"
        print("  ✓ Correctly confirmed with 'yes please'")
        
        print("\n✅ PASSED: Tolerant confirmation → yes please")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_scenario_3_negative_confirmation():
    """Test: User denies clarification with 'no'"""
    print("\n" + "="*70)
    print("TEST 3: Negative Confirmation → 'no'")
    print("="*70)
    
    app, db, context, ConversationThread = setup_test_context()
    from services.message_orchestrator import MessageOrchestrator
    
    try:
        orchestrator = MessageOrchestrator()
        
        # Step 1: Setup IDs
        site_id = 'test_site'
        session_id = 'test_session_3'
        print(f"✓ Setup site_id={site_id}, session_id={session_id}")
        
        # Step 2: Send ambiguous message
        print("\n[USER] 'fees'")
        result = orchestrator.process_message(site_id, session_id, "fees")
        
        # Get thread
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result.get('intent', {}).get('name', 'unknown')} (confidence: {result.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        assert thread.pending_clarification is not None, "Should have pending_clarification"
        print("  ✓ Entered clarification band")
        
        # Step 3: Deny with "no"
        print("\n[USER] 'no'")
        result2 = orchestrator.process_message(site_id, session_id, "no")
        
        # Reload thread
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        print(f"  Detected intent: {result2.get('intent', {}).get('name', 'unknown')} (confidence: {result2.get('intent', {}).get('confidence', 0):.2f})")
        print(f"  Pending clarification: {thread.pending_clarification}")
        print(f"  Trace: {thread.execution_trace[-3:]}")
        
        # Verify denial cleared pending but continued to detection
        assert thread.pending_clarification is None, "Should clear pending_clarification"
        assert any('clarification_denied' in str(entry) for entry in thread.execution_trace[-3:]), "Should log denial"
        print("  ✓ Correctly denied and re-detected")
        
        print("\n✅ PASSED: Negative confirmation → no")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("PHASE 1 CRITICAL FIX VALIDATION")
    print("Testing clarification confirmation execution order")
    print("="*70)
    
    results = []
    
    # Run all 3 scenarios
    try:
        results.append(("Test 1: Normal yes", test_scenario_1_normal_clarification()))
        results.append(("Test 2: Tolerant yes please", test_scenario_2_tolerant_confirmation()))
        results.append(("Test 3: Deny with no", test_scenario_3_negative_confirmation()))
    except Exception as e:
        print(f"\n⚠️  Warning: Tests could not complete: {e}")
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
        print("✅ ALL TESTS PASSED - Ready for concurrency validation")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review output above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
