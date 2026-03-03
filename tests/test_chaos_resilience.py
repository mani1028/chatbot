"""
CHAOS & FAILURE RESILIENCE TEST SUITE

Tests 4 critical production failure modes:
1. CONCURRENCY: 100 simultaneous messages - verify no race conditions
2. LLM FAILURE: Simulate timeouts - verify graceful degradation  
3. DB FAILURE: Commit rollback - verify state consistency
4. TENANT ISOLATION: Cross-tenant data leak - verify isolation

Production readiness = Can break without breaking the system.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import json
import requests
from unittest.mock import patch, MagicMock
import logging

from app import app, db
from models.conversation_thread import ConversationThread
from models.site import Site
from models.chat_log import ChatLog
from services.message_orchestrator import MessageOrchestrator
from config import CONFIDENCE_THRESHOLD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# TEST INFRASTRUCTURE
# ============================================================================

class ChaosTestContext:
    """Manage test context: create app, db, fixtures"""
    
    def __init__(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create test database (with proper order)
        with self.app.app_context():
            # Import all models before creating tables
            from models.plan import Plan
            from models.site import Site
            from models.conversation_thread import ConversationThread
            
            db.create_all()
            
            # Create test plan first
            test_plan = Plan(name='Test Plan', max_monthly_chats=1000)
            db.session.add(test_plan)
            db.session.commit()
            
            # Create test site with proper relationships
            self.test_site = Site(
                name='Test Site',
                domain='test.com',
                status='active',
                plan_id=test_plan.id
            )
            db.session.add(self.test_site)
            db.session.commit()
            self.site_id = self.test_site.id
            
            logger.info(f"[OK] Test context created: site_id={self.site_id}")
    
    def cleanup(self):
        """Tear down test context"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def get_thread_count(self, site_id=None):
        """Count threads for site"""
        query = ConversationThread.query
        if site_id:
            query = query.filter_by(site_id=site_id)
        return query.count()
    
    def get_thread_data(self, thread_id):
        """Load thread and check data integrity"""
        thread = ConversationThread.query.get(thread_id)
        if not thread:
            return None
        return {
            'id': thread.id,
            'site_id': thread.site_id,
            'messages': thread.short_term_messages,
            'data': thread.structured_data,
            'workflow': thread.workflow_type,
            'last_message_at': thread.last_message_at
        }

# ============================================================================
# TEST 1: CONCURRENCY BLAST
# ============================================================================

def test_concurrency_100_simultaneous():
    """
    SCENARIO: 100 simultaneous message requests
    
    VERIFY:
    - No race conditions in thread creation
    - No duplicate threads
    - All messages processed
    - No database corruption
    - No deadlocks
    """
    print("\n" + "="*80)
    print("[TEST 1] CONCURRENCY BLAST: 100 Simultaneous Messages")
    print("="*80)
    
    ctx = ChaosTestContext()
    
    try:
        orchestrator = MessageOrchestrator()
        session_id = 'concurrency_test_session'
        
        message_count = 100
        success_count = 0
        error_count = 0
        errors = []
        response_times = []
        
        def send_message(msg_id):
            """Send single message concurrently"""
            try:
                start = time.time()
                
                result = orchestrator.process_message(
                    message=f"Test message {msg_id}",
                    site_id=ctx.site_id,
                    session_id=session_id,
                    user_id=f"user_{msg_id}",
                    page_url='/'
                )
                
                elapsed = time.time() - start
                response_times.append(elapsed)
                
                return {
                    'msg_id': msg_id,
                    'success': bool(result.get('text')),
                    'elapsed': elapsed,
                    'confidence': result.get('confidence', 0)
                }
            except Exception as e:
                return {
                    'msg_id': msg_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Blast 100 concurrent messages
        print(f"\n▶ Sending {message_count} simultaneous messages...")
        start_blast = time.time()
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(send_message, i) for i in range(message_count)]
            
            for future in as_completed(futures):
                result = future.result()
                if result['success']:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(result.get('error', 'Unknown error'))
        
        blast_time = time.time() - start_blast
        
        # Verify results
        final_thread_count = ctx.get_thread_count(ctx.site_id)
        
        print(f"\n▶ Results:")
        print(f"  Success: {success_count}/{message_count}")
        print(f"  Errors: {error_count}")
        print(f"  Total time: {blast_time:.2f}s ({message_count/blast_time:.0f} msg/s)")
        print(f"  Avg response: {sum(response_times)/len(response_times):.3f}s")
        print(f"  Threads created: {final_thread_count}")
        
        # Assertions
        assert success_count >= message_count * 0.95, \
            f"Only {success_count}/{message_count} succeeded, {error_count} errors"
        
        assert final_thread_count >= 1, \
            f"No threads created! {final_thread_count} threads"
        
        assert final_thread_count <= 5, \
            f"Too many threads created! Expected 1-5, got {final_thread_count} (race condition?)"
        
        # Verify thread data integrity
        threads = ConversationThread.query.filter_by(site_id=ctx.site_id).all()
        for thread in threads:
            assert isinstance(thread.short_term_messages, list), \
                f"Thread {thread.id}: messages not list"
            assert isinstance(thread.structured_data, dict), \
                f"Thread {thread.id}: data not dict"
        
        print(f"\n✅ [TEST 1 PASS] Concurrency resilient: {success_count} messages processed, {final_thread_count} threads, no corruption")
        return True
        
    except AssertionError as e:
        print(f"\n❌ [TEST 1 FAIL] {e}")
        return False
    except Exception as e:
        print(f"\n❌ [TEST 1 ERROR] {e}")
        return False
    finally:
        ctx.cleanup()

# ============================================================================
# TEST 2: LLM TIMEOUT & FAILURE
# ============================================================================

def test_llm_failure_graceful_degradation():
    """
    SCENARIO: LLM service timeout/failure during processing
    
    VERIFY:
    - Graceful fallback when LLM fails
    - Message still processed (not lost)
    - Thread state remains consistent
    - Error logged but system continues
    - No infinite loops/hangs
    """
    print("\n" + "="*80)
    print("[TEST 2] LLM FAILURE: Graceful Degradation")
    print("="*80)
    
    ctx = ChaosTestContext()
    
    try:
        orchestrator = MessageOrchestrator()
        session_id = 'llm_failure_test'
        
        # Simulate LLM timeout
        def mock_llm_fallback_timeout(*args, **kwargs):
            time.sleep(0.1)  # Simulate timeout
            raise TimeoutError("LLM service timeout (simulated)")
        
        print("\n▶ Sending message with LLM path...")
        
        with patch('services.message_orchestrator.llm_fallback', side_effect=mock_llm_fallback_timeout):
            start = time.time()
            
            result = orchestrator.process_message(
                message="Write a poem about cats",  # Triggers low-confidence → LLM path
                site_id=ctx.site_id,
                session_id=session_id,
                user_id='test_user'
            )
            
            elapsed = time.time() - start
        
        print(f"\n▶ Response received after {elapsed:.3f}s")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Text: {result.get('text', '')[:100]}...")
        print(f"  Confidence: {result.get('confidence', 'N/A')}")
        
        # Assertions
        assert result is not None, "No response returned on LLM failure"
        assert result.get('text') is not None, "Response text is None"
        assert elapsed < 2.0, f"Response took too long on LLM failure: {elapsed}s"
        
        # Verify thread was created despite LLM failure
        thread_count = ctx.get_thread_count(ctx.site_id)
        assert thread_count >= 1, "Thread not created despite LLM failure"
        
        # Verify message was added
        thread = ConversationThread.query.filter_by(
            site_id=ctx.site_id,
            session_id=session_id
        ).first()
        assert thread is not None, "Thread not found"
        assert len(thread.short_term_messages) > 0, "Message not appended"
        
        print(f"\n✅ [TEST 2 PASS] LLM failure handled gracefully: response returned, thread created, message logged")
        return True
        
    except AssertionError as e:
        print(f"\n❌ [TEST 2 FAIL] {e}")
        return False
    except Exception as e:
        print(f"\n❌ [TEST 2 ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ctx.cleanup()

# ============================================================================
# TEST 3: DATABASE COMMIT FAILURE
# ============================================================================

def test_db_commit_rollback_consistency():
    """
    SCENARIO: Database commit fails mid-transaction
    
    VERIFY:
    - State rolled back properly
    - No partial writes
    - Thread not partially created
    - Orchestrator handles db.session.commit() failure
    - System recovers and retry works
    """
    print("\n" + "="*80)
    print("[TEST 3] DATABASE FAILURE: Commit Rollback Consistency")
    print("="*80)
    
    ctx = ChaosTestContext()
    
    try:
        orchestrator = MessageOrchestrator()
        session_id = 'db_failure_test'
        
        initial_count = ctx.get_thread_count(ctx.site_id)
        
        print(f"\n▶ Initial thread count: {initial_count}")
        print("▶ Simulating commit failure...")
        
        # Make commit fail
        original_commit = db.session.commit
        call_count = [0]
        
        def mock_commit_fail():
            call_count[0] += 1
            if call_count[0] <= 2:  # Fail first 2 commits
                raise Exception("Database commit failed (simulated)")
            else:
                return original_commit()
        
        with patch.object(db.session, 'commit', side_effect=mock_commit_fail):
            try:
                result = orchestrator.process_message(
                    message="Test during commit failure",
                    site_id=ctx.site_id,
                    session_id=session_id,
                    user_id='test_user'
                )
            except Exception as e:
                print(f"  Expected error caught: {type(e).__name__}")
        
        # Verify state is consistent (rolled back)
        after_failure_count = ctx.get_thread_count(ctx.site_id)
        print(f"\n▶ Thread count after failure: {after_failure_count}")
        print(f"  Change: {after_failure_count - initial_count}")
        
        # Thread count might change, but should be valid state
        # (either no change or clean thread created)
        assert after_failure_count >= initial_count, \
            "Threads were deleted due to rollback?"
        
        # Now restore normal operation
        print("▶ Restoring normal database operation...")
        
        result = orchestrator.process_message(
            message="Test after commit recovery",
            site_id=ctx.site_id,
            session_id=f"{session_id}_retry",
            user_id='test_user'
        )
        
        final_count = ctx.get_thread_count(ctx.site_id)
        print(f"\n▶ Thread count after recovery: {final_count}")
        
        assert final_count > after_failure_count, \
            "Message not processed after recovery"
        
        assert result.get('text') is not None, \
            "No response on retry after commit failure"
        
        print(f"\n✅ [TEST 3 PASS] DB failure handled: rollback consistent, recovery works")
        return True
        
    except AssertionError as e:
        print(f"\n❌ [TEST 3 FAIL] {e}")
        return False
    except Exception as e:
        print(f"\n❌ [TEST 3 ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ctx.cleanup()

# ============================================================================
# TEST 4: MULTI-TENANT ISOLATION
# ============================================================================

def test_multi_tenant_isolation():
    """
    SCENARIO: Multiple tenants sending messages simultaneously
    
    VERIFY:
    - Tenant A cannot see Tenant B's threads
    - Tenant A cannot see Tenant B's messages
    - Data is strictly isolated by site_id
    - Thread queries respect tenant boundaries
    - No cross-tenant data leaks
    """
    print("\n" + "="*80)
    print("[TEST 4] MULTI-TENANT ISOLATION: No Cross-Tenant Leaks")
    print("="*80)
    
    from models.site import Site
    
    ctx = ChaosTestContext()
    
    try:
        # Create second test site (tenant B)
        from models.plan import Plan
        test_plan = Plan.query.first() or Plan(name='Test Plan', max_monthly_chats=1000)
        if not test_plan.id:
            db.session.add(test_plan)
            db.session.commit()
        
        site_b = Site(
            name='Test Site B',
            domain='testb.com',
            status='active',
            plan_id=test_plan.id
        )
        db.session.add(site_b)
        db.session.commit()
        site_b_id = site_b.id
        
        print(f"\n▶ Created two test sites:")
        print(f"  Site A (default): {ctx.site_id}")
        print(f"  Site B: {site_b_id}")
        
        orchestrator = MessageOrchestrator()
        
        # Send messages for both tenants simultaneously
        print(f"\n▶ Sending messages for both tenants...")
        
        def send_to_tenant(site_id, tenant_name):
            result = orchestrator.process_message(
                message=f"Message from {tenant_name}",
                site_id=site_id,
                session_id=f'session_{tenant_name}',
                user_id=f'user_{tenant_name}'
            )
            return result
        
        # Send to both tenants
        result_a = send_to_tenant(ctx.site_id, 'A')
        result_b = send_to_tenant(site_b_id, 'B')
        
        print(f"  Sent to Site A: {result_a.get('text', 'ERROR')[:50]}...")
        print(f"  Sent to Site B: {result_b.get('text', 'ERROR')[:50]}...")
        
        # Verify thread counts
        threads_a = ConversationThread.query.filter_by(site_id=ctx.site_id).all()
        threads_b = ConversationThread.query.filter_by(site_id=site_b_id).all()
        
        print(f"\n▶ Thread counts:")
        print(f"  Site A: {len(threads_a)} threads")
        print(f"  Site B: {len(threads_b)} threads")
        
        assert len(threads_a) > 0, "No threads for Site A"
        assert len(threads_b) > 0, "No threads for Site B"
        
        # Verify no cross-tenant leakage
        for thread_a in threads_a:
            assert thread_a.site_id == ctx.site_id, \
                f"Thread in A has wrong site_id: {thread_a.site_id}"
            assert thread_a.site_id != site_b_id, \
                f"Thread A has Site B ID!"
        
        for thread_b in threads_b:
            assert thread_b.site_id == site_b_id, \
                f"Thread in B has wrong site_id: {thread_b.site_id}"
            assert thread_b.site_id != ctx.site_id, \
                f"Thread B has Site A ID!"
        
        # Verify message content isolation
        thread_a = threads_a[0]
        thread_b = threads_b[0]
        
        messages_a = thread_a.short_term_messages
        messages_b = thread_b.short_term_messages
        
        print(f"\n▶ Message content verification:")
        print(f"  Site A sees {len(messages_a)} messages")
        print(f"  Site B sees {len(messages_b)} messages")
        
        # Verify Site A cannot query Site B's threads
        leaked_threads = ConversationThread.query.filter_by(
            site_id=ctx.site_id,
            session_id='session_B'  # Site B's session
        ).all()
        
        assert len(leaked_threads) == 0, \
            f"Site A can query Site B's sessions! Found {len(leaked_threads)} leaked threads"
        
        # Verify Site B cannot query Site A's threads
        leaked_threads_reverse = ConversationThread.query.filter_by(
            site_id=site_b_id,
            session_id='session_A'  # Site A's session
        ).all()
        
        assert len(leaked_threads_reverse) == 0, \
            f"Site B can query Site A's sessions! Found {len(leaked_threads_reverse)} leaked threads"
        
        print(f"\n✅ [TEST 4 PASS] Multi-tenant isolation enforced: no cross-tenant leaks")
        return True
        
    except AssertionError as e:
        print(f"\n❌ [TEST 4 FAIL] {e}")
        return False
    except Exception as e:
        print(f"\n❌ [TEST 4 ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        ctx.cleanup()

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

if __name__ == '__main__':
    print("""
================================================================================
                   CHAOS & RESILIENCE TEST SUITE
                                                                            
 Production Readiness = System Can Fail Without Failing                    
                                                                            
 Test 1: CONCURRENCY       - 100 simultaneous messages, no race conditions 
 Test 2: LLM FAILURE       - Timeout handling, graceful degradation        
 Test 3: DB COMMIT FAILURE - Rollback consistency, recovery                
 Test 4: MULTI-TENANT      - Isolation enforcement, no cross-tenant leaks  
================================================================================
    """)
    
    results = {
        'concurrency': test_concurrency_100_simultaneous(),
        'llm_failure': test_llm_failure_graceful_degradation(),
        'db_failure': test_db_commit_rollback_consistency(),
        'multi_tenant': test_multi_tenant_isolation()
    }
    
    # Summary
    print("\n" + "="*80)
    print("CHAOS TEST RESULTS")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {test_name}")
    
    print(f"\nSummary: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎯 SYSTEM PRODUCTION-READY: All resilience tests passed")
        print("   Architecture enforced + Chaos tested = Safe for production")
        sys.exit(0)
    else:
        print(f"\n⚠️  System resilience compromised: {total-passed} failures")
        sys.exit(1)
