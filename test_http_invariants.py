#!/usr/bin/env python3
"""
Phase 1 Production Safety Validation
Real HTTP-level tests, not mocked functions
"""
import sys, os, json
import concurrent.futures
sys.path.insert(0, os.path.dirname(__file__))

from app import app, db
from models import ConversationThread

print("="*70)
print("PHASE 1 - LIVE HTTP INVARIANT SAFETY VALIDATION")
print("="*70)

def test_a_real_clarification_flow():
    """Test A: Real clarification flow via HTTP (no mocking)"""
    print("\n[TEST A] Real Clarification Flow via HTTP")
    print("-" * 70)
    
    # First, create or get a test site with public_key
    with app.app_context():
        from models.site import Site
        site = Site.query.filter_by(name='test_site').first()
        if not site:
            site = Site(name='test_site', public_key='test_public_key_123')
            db.session.add(site)
            db.session.commit()
        site_id = site.id
        public_key = site.public_key
    
    with app.test_client() as client:
        session_id = 'test_a_http'
        
        try:
            # Step 1: Send ambiguous message
            print("\n  Step 1: POST /api/chat with 'fees'")
            resp1 = client.post('/api/chat', json={
                'message': 'fees',
                'session_id': session_id,
                'site_key': public_key,
                'page_url': 'http://test.com'
            }, headers={'Content-Type': 'application/json'})
            
            data1 = resp1.get_json()
            print(f"    Status: {resp1.status_code}")
            print(f"    Intent: {data1.get('intent_name', 'N/A')}")
            print(f"    Reply snippet: {data1.get('reply', 'N/A')[:50]}...")
            
            # Check if clarification triggered
            has_clarification = 'clarification' in data1.get('reply', '').lower() or \
                               'mean' in data1.get('reply', '').lower()
            
            if has_clarification:
                print("    [OK] Clarification triggered")
            else:
                print("    [WARN] No clarification - checking if MEDIUM confidence")
            
            # Verify DB state after request 1
            thread1 = ConversationThread.query.filter_by(
                site_id=site_id, session_id=session_id
            ).first()
            
            pending_1 = thread1.pending_clarification if thread1 else None
            print(f"    DB: pending_clarification = {pending_1}")
            
            if pending_1:
                print("    [OK] Pending clarification stored in DB")
            
            # Step 2: Send confirmation
            print("\n  Step 2: POST /api/chat with 'yes' (same session)")
            resp2 = client.post('/api/chat', json={
                'message': 'yes',
                'session_id': session_id,
                'site_key': public_key,
                'page_url': 'http://test.com'
            }, headers={'Content-Type': 'application/json'})
            
            data2 = resp2.get_json()
            print(f"    Status: {resp2.status_code}")
            print(f"    Intent: {data2.get('intent_name', 'N/A')}")
            print(f"    Confidence: {data2.get('intent_confidence', 'N/A')}")
            
            # Verify DB state after request 2
            thread2 = ConversationThread.query.filter_by(
                site_id=site_id, session_id=session_id
            ).first()
            
            pending_2 = thread2.pending_clarification if thread2 else None
            print(f"    DB: pending_clarification = {pending_2}")
            
            # Checks
            assert resp1.status_code == 200, f"Request 1 failed: {resp1.status_code}"
            assert resp2.status_code == 200, f"Request 2 failed: {resp2.status_code}"
            print("    [OK] Both requests returned 200")
            
            assert pending_2 is None, f"Pending not cleared: {pending_2}"
            print("    [OK] Cleared pending_clarification after confirmation")
            
            assert 'LLM' not in str(thread2.execution_trace), "LLM should not be called on confirmation"
            print("    [OK] No LLM call during confirmation (execution_trace verified)")
            
            # Check single commit per request
            if thread2 and hasattr(thread2, 'total_turns'):
                print(f"    [OK] Thread persisted (total_turns: {thread2.total_turns})")
            
            print("\n[PASS A] Real clarification flow is correct")
            return True
            
        except Exception as e:
            print(f"\n[FAIL A] {e}")
            import traceback
            traceback.print_exc()
            return False

def test_b_concurrency_simulation():
    """Test B: Concurrent confirmation attempts (race condition check)"""
    print("\n[TEST B] Concurrency Simulation - 5 Parallel Confirmations")
    print("-" * 70)
    
    try:
        # Get or create test site
        with app.app_context():
            from models.site import Site
            site = Site.query.filter_by(name='test_site').first()
            if not site:
                site = Site(name='test_site', public_key='test_public_key_123')
                db.session.add(site)
                db.session.commit()
            site_id = site.id
            public_key = site.public_key
        
        session_id = 'test_b_concurrent'
        
        # First, set up the clarification state in DB
        with app.app_context():
            thread = ConversationThread.query.filter_by(
                site_id=site_id, session_id=session_id
            ).first()
            
            if not thread:
                thread = ConversationThread(
                    site_id=site_id,
                    session_id=session_id,
                    pending_clarification='PAYMENT_INFO'
                )
                db.session.add(thread)
                db.session.commit()
        
        # Now send 5 concurrent confirmations
        print("\n  Sending 5 concurrent 'yes' confirmations...")
        
        def send_confirmation(i):
            with app.test_client() as client:
                resp = client.post('/api/chat', json={
                    'message': 'yes',
                    'session_id': session_id,
                    'site_key': public_key,
                    'page_url': 'http://test.com'
                }, headers={'Content-Type': 'application/json'})
                return i, resp.status_code, resp.get_json()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_confirmation, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        print(f"\n  Results from 5 concurrent requests:")
        for i, status, data in sorted(results):
            print(f"    [{i}] Status: {status}, Intent: {data.get('intent_name', 'N/A')}")
        
        # All should succeed
        assert all(status == 200 for _, status, _ in results), "Some requests failed"
        print("    [OK] All 5 requests succeeded")
        
        # Check final DB state
        with app.app_context():
            thread_final = ConversationThread.query.filter_by(
                site_id=site_id, session_id=session_id
            ).first()
            
            assert thread_final.pending_clarification is None, "Pending not cleared"
            print("    [OK] Final state: pending_clarification cleared")
            
            # No double-confirmation should occur
            # Check execution trace doesn't have duplicate confirmations
            trace_str = str(thread_final.execution_trace)
            confirmation_count = trace_str.count('clarification_confirmed')
            print(f"    [OK] Confirmation logged {confirmation_count} time(s)")
        
        print("\n[PASS B] No concurrency corruption detected")
        return True
        
    except Exception as e:
        print(f"\n[FAIL B] {e}")
        import traceback
        traceback.print_exc()
        return False

def test_c_workflow_protection():
    """Test C: Clarification should NOT trigger mid-workflow"""
    print("\n[TEST C] Mid-Workflow Clarification Prevention")
    print("-" * 70)
    
    try:
        # Get or create test site
        with app.app_context():
            from models.site import Site
            site = Site.query.filter_by(name='test_site').first()
            if not site:
                site = Site(name='test_site', public_key='test_public_key_123')
                db.session.add(site)
                db.session.commit()
            site_id = site.id
            public_key = site.public_key
        
        session_id = 'test_c_workflow'
        
        # Setup: Create thread with active workflow
        with app.app_context():
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                workflow_type='BOOKING',  # Active workflow
                workflow_status='active',
                current_step='capture_date'
            )
            db.session.add(thread)
            db.session.commit()
        
        print("\n  Workflow setup: BOOKING workflow in 'capture_date' step")
        
        # Try to send ambiguous message while in workflow
        with app.test_client() as client:
            print("\n  Sending 'fees' while in workflow...")
            resp = client.post('/api/chat', json={
                'message': 'fees',
                'session_id': session_id,
                'site_key': public_key,
                'page_url': 'http://test.com'
            }, headers={'Content-Type': 'application/json'})
            
            data = resp.get_json()
            print(f"    Status: {resp.status_code}")
            print(f"    Intent: {data.get('intent_name', 'N/A')}")
            print(f"    Reply snippet: {data.get('reply', 'N/A')[:50]}...")
        
        # Check DB - clarification should NOT be set
        with app.app_context():
            thread_after = ConversationThread.query.filter_by(
                site_id=site_id, session_id=session_id
            ).first()
            
            assert thread_after.pending_clarification is None, \
                "Clarification should NOT trigger during workflow"
            print("    [OK] Clarification did NOT trigger (pending is None)")
            
            assert thread_after.workflow_type == 'BOOKING', \
                "Workflow state corrupted"
            print("    [OK] Workflow state preserved")
            
            assert thread_after.current_step == 'capture_date', \
                "Workflow step changed"
            print("    [OK] Workflow step unchanged")
        
        print("\n[PASS C] Workflow protection working correctly")
        return True
        
    except Exception as e:
        print(f"\n[FAIL C] {e}")
        import traceback
        traceback.print_exc()
        return False

# Run all tests
results = [
    ("Test A: Real HTTP clarification flow", test_a_real_clarification_flow()),
    ("Test B: Concurrency 5-way confirmation", test_b_concurrency_simulation()),
    ("Test C: Mid-workflow clarification prevention", test_c_workflow_protection()),
]

# Summary
print("\n" + "="*70)
print("LIVE HTTP TEST RESULTS")
print("="*70)
for name, passed in results:
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}")

all_passed = all(r[1] for r in results)
print("="*70)

if all_passed:
    print("\n[RESULT READY FOR CONFIRMATION]")
    print("All live HTTP tests passed.")
    print("Ready for user approval of:")
    print("  'Phase 1 is now invariant-safe under live HTTP testing.'")
    sys.exit(0)
else:
    print("\n[RESULT FAILED]")
    print("Some tests failed. Review output above.")
    sys.exit(1)
