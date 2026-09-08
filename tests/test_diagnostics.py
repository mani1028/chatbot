"""
Performance diagnostics test - measures per-stage latencies.
Logs timing for: intent detection, rule engine, database queries, etc.
"""

import logging
import sys
from app import app
from services.message_orchestrator import MessageOrchestrator

# Configure logging to show timing info
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s: %(message)s',
    stream=sys.stdout
)

def run_diagnostics():
    """Run diagnostic tests and capture timing"""
    
    print("\n" + "=" * 70)
    print("PERFORMANCE DIAGNOSTICS - Intent & Rule Engine Timing")
    print("=" * 70 + "\n")
    
    with app.app_context():
        orchestrator = MessageOrchestrator()
        session_id = 'diag-test-session'
        site_id = 2
        
        test_messages = [
            ('hello', 'Simple greeting'),
            ('what are your hours', 'Business hours - intent lookup'),
            ('contact us', 'Contact info - template substitution'),
            ('help me please', 'Generic help with intent detection'),
        ]
        
        for msg, description in test_messages:
            print(f"\n{'─' * 70}")
            print(f"Test: {description}")
            print(f"Message: \"{msg}\"")
            print(f"{'─' * 70}")
            
            result = orchestrator.process_message(
                site_id=site_id,
                session_id=session_id,
                message=msg
            )
            
            print(f"\nResult:")
            print(f"  Intent: {result.get('intent_name', 'N/A')}")
            print(f"  Reply: {result.get('reply', 'N/A')[:80]}...")
            print()


if __name__ == '__main__':
    run_diagnostics()
