from core.intent_engine import detect_intent
from models import Intent, FAQ
from services.response_builder import build_response
from workflows import handler as workflow_handler
from config import CONFIDENCE_THRESHOLD
from database import db
import random
import traceback  # Added for debugging

def handle_message(message: str, client_id: int, site_id: int = 0) -> dict:
    """Main pipeline entry. Returns a response dict with keys:
       - text
       - intent_name
       - intent_type
       - confidence
       - handoff (optional)
    """
    # 1. Detect Intent
    result = detect_intent(message, site_id)
    intent_name = result.get('intent_name')
    confidence = result.get('confidence', 0.0)

    # If no intent detected return fallback
    if intent_name in (None, 'UNKNOWN'):
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': 'UNKNOWN'}

    # 2. Fetch Intent from DB
    # Prefer site-specific intent, fallback to global (0)
    intent = Intent.query.filter((Intent.site_id == site_id) | (Intent.site_id == 0)).filter_by(intent_name=intent_name).first()

    # If intent not in DB (only in code?), return what detect_intent suggested
    if not intent:
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}

    # 3. Check Confidence
    threshold = getattr(intent, 'confidence_threshold', CONFIDENCE_THRESHOLD)
    if confidence < threshold:
        return {
            'text': random.choice(['I can connect you with a human for help.', 'Would you like me to connect you with support?']), 
            'confidence': confidence, 
            'intent_name': intent_name, 
            'handoff': 'HUMAN'
        }

    # 4. Handle Intent Types
    itype = (intent.intent_type or 'info').lower()
    
    if itype == 'action':
        # Workflow Logic
        wf = intent.workflows.first()
        if wf:
            func_name = wf.function_name
            # call workflow handler dynamically
            func = getattr(workflow_handler, func_name, None)
            if func:
                try:
                    # FORCE client_id to int to prevent database errors
                    safe_client_id = int(client_id) if str(client_id).isdigit() else 1
                    
                    # Execute workflow function
                    data = func(client_id=safe_client_id, message=message)
                    
                    # Prepare response: Use template if exists, else raw data
                    if intent.response:
                        text = build_response(intent.response, safe_client_id)
                    else:
                        text = str(data)
                        
                    return {'text': text, 'confidence': confidence, 'intent_name': intent_name, 'data': data}
                
                except Exception as e:
                    print(f"❌ WORKFLOW ERROR ({func_name}): {str(e)}")
                    traceback.print_exc() # Print full error to console
                    return {'text': 'Sorry, something went wrong. Please try again.', 'confidence': 0.0, 'intent_name': intent_name}
        
        # Fallback if no workflow found
        return {'text': intent.response or 'Action intent configured but no workflow found.', 'confidence': confidence, 'intent_name': intent_name}

    else:
        # Info Intent Logic
        safe_client_id = int(client_id) if str(client_id).isdigit() else 1
        
        if intent.response:
            text = build_response(intent.response, safe_client_id)
            return {'text': text, 'confidence': confidence, 'intent_name': intent_name}

        # Fallback to FAQ search
        if intent.sector:
            faq = FAQ.query.filter_by(sector=intent.sector).first()
        else:
            faq = FAQ.query.filter(FAQ.question.ilike(f"%{intent_name}%")).first()

        if faq:
            return {'text': faq.answer, 'confidence': confidence, 'intent_name': intent_name}

        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}