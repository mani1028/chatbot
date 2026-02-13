from core.intent_engine import detect_intent
from models import Intent
from services.response_builder import build_response
from workflows import handler as workflow_handler
from config import CONFIDENCE_THRESHOLD
import random

def handle_message(message: str, client_id: int, site_id: int = 0) -> dict:
    result = detect_intent(message, site_id)
    intent_name = result.get('intent_name')
    confidence = result.get('confidence', 0.0)

    if intent_name in (None, 'UNKNOWN'):
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': 'UNKNOWN'}

    intent = Intent.query.filter((Intent.site_id == site_id) | (Intent.site_id == 0)).filter_by(intent_name=intent_name).first()

    if not intent:
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}

    threshold = getattr(intent, 'confidence_threshold', CONFIDENCE_THRESHOLD)
    if confidence < threshold:
        return {'text': 'I can connect you with a human for help.', 'confidence': confidence, 'intent_name': intent_name, 'handoff': 'HUMAN'}

    itype = (intent.intent_type or 'info').lower()
    if itype == 'action':
        wf = intent.workflows.first()
        if wf:
            func_name = wf.function_name
            func = getattr(workflow_handler, func_name, None)
            if func:
                try:
                    data = func(client_id=client_id, message=message)
                    text = build_response(intent.response, client_id) if intent.response else str(data)
                    return {'text': text, 'confidence': confidence, 'intent_name': intent_name, 'data': data}
                except Exception as e:
                    return {'text': 'Sorry, something went wrong while processing your request.', 'confidence': 0.0, 'intent_name': intent_name}
        return {'text': intent.response or 'Action intent configured but no workflow found.', 'confidence': confidence, 'intent_name': intent_name}

    else:
        if intent.response:
            text = build_response(intent.response, client_id)
            return {'text': text, 'confidence': confidence, 'intent_name': intent_name}

        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}