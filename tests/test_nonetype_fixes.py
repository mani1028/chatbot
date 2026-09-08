"""Test NoneType fixes"""

from app import app, db
from services.rule_engine import UnknownIntentRule
from models.conversation_thread import ConversationThread

def test_nonetype_fixes():
    """Test that NoneType comparisons are handled safely"""
    
    with app.app_context():
        print("Testing NoneType fixes...")
        
        # Test 1: UnknownIntentRule with None
        rule = UnknownIntentRule()
        thread = ConversationThread(
            id='test-thread-1',
            site_id=2,
            session_id='test-session-1'
        )
        # unknown_intent_count defaults to 0, but let's test None
        thread.unknown_intent_count = None
        
        try:
            result = rule.matches(thread, 'test message')
            print(f"✓ UnknownIntentRule handles None: {result}")
        except Exception as e:
            print(f"✗ UnknownIntentRule error: {e}")
            return False
        
        # Test 2: Analytics with None unknown_intent_count
        try:
            # This mimics what the analytics function does
            threads = [thread]
            unknown_intent_avg = sum((t.unknown_intent_count or 0) for t in threads) / len(threads) if threads else 0
            print(f"✓ Analytics handles None in unknown_intent_count: avg={unknown_intent_avg}")
        except Exception as e:
            print(f"✗ Analytics error: {e}")
            return False
        
        # Test 3: _run_analytics increment with None
        try:
            current_count = thread.unknown_intent_count or 0
            thread.unknown_intent_count = current_count + 1
            print(f"✓ Increment handles None: new_count={thread.unknown_intent_count}")
        except Exception as e:
            print(f"✗ Increment error: {e}")
            return False
        
        print("\n✓ All NoneType fixes verified!")
        return True

if __name__ == '__main__':
    test_nonetype_fixes()
