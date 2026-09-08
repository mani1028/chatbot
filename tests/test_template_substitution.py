"""Test template variable substitution for multiple intents"""

from app import app
from services.message_orchestrator import MessageOrchestrator

def test_template_substitution():
    with app.app_context():
        orchestrator = MessageOrchestrator()
        session_id = 'test-substitution'
        site_id = 2
        
        # Test template variables
        test_messages = [
            ('where are you located', 'location_address'),
            ('how can I contact you', 'contact_info'),
            ('what is your pricing', 'pricing_general'),
        ]
        
        print("=" * 60)
        print("TEMPLATE VARIABLE SUBSTITUTION TEST")
        print("=" * 60)
        
        for msg, expected_intent in test_messages:
            result = orchestrator.process_message(
                site_id=site_id,
                session_id=session_id,
                message=msg
            )
            print(f'\nMessage: "{msg}"')
            print(f'Intent: {result["intent_name"]}')
            print(f'Response: {result["reply"]}')
            
            # Check if template variables are replaced
            if '{' in result['reply']:
                print('WARNING: Template variables still present!')
            else:
                print('SUCCESS: Template variables replaced')

if __name__ == '__main__':
    test_template_substitution()
