"""Test response time with fixes"""

import time
from app import app
from services.message_orchestrator import MessageOrchestrator

def test_response_time():
    """Test that response times are reasonable with fixes"""
    
    with app.app_context():
        orchestrator = MessageOrchestrator()
        session_id = 'perf-test-session'
        site_id = 2
        
        # Test messages  
        test_messages = [
            ('hello', 1.5),  # Expected ~1.5s first request (model loading)
            ('what are your timings', 1.0),  # Expected ~1.0s (faster on repeat)
            ('contact info', 1.0),  # Expected ~1.0s
        ]
        
        print("=" * 60)
        print("PERFORMANCE TEST - Message Processing")
        print("=" * 60)
        
        for msg, max_time in test_messages:
            start = time.time()
            result = orchestrator.process_message(
                site_id=site_id,
                session_id=session_id,
                message=msg
            )
            elapsed = time.time() - start
            
            status = "PASS" if elapsed < max_time else "SLOW"
            print(f"\n[{status}]")
            print(f"Message: \"{msg}\"")
            print(f"Time: {elapsed:.2f}s (max: {max_time}s)")
            print(f"Intent: {result['reply'][:60]}...")
            
            # Check for errors
            if 'error' in result:
                print(f"ERROR: {result['error']}")

if __name__ == '__main__':
    test_response_time()
