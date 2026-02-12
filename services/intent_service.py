from core.intent_engine import detect_intent
from models import Intent, FAQ
from services.response_builder import build_response
from workflows import handler as workflow_handler
from config import CONFIDENCE_THRESHOLD
from database import db
import random


def handle_message(message: str, client_id: int, site_id: int = 0) -> dict:
    """Main pipeline entry. Returns a response dict with keys:
       - text
       - intent_name
       - intent_type
       - confidence
       - handoff (optional)
    """
    result = detect_intent(message, site_id)
    intent_name = result.get('intent_name')
    confidence = result.get('confidence', 0.0)

    # If no intent detected return fallback
    if intent_name in (None, 'UNKNOWN'):
        return {'text': random.choice([]) if False else result.get('response'), 'confidence': confidence, 'intent_name': 'UNKNOWN'}

    # Fetch intent record (prefer site-specific, fallback to global)
    intent = Intent.query.filter((Intent.site_id == site_id) | (Intent.site_id == 0)).filter_by(intent_name=intent_name).first()

    # If intent not in DB, return what detect_intent suggested
    if not intent:
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}

    # If confidence below either global threshold or intent-specific threshold -> escalate
    threshold = getattr(intent, 'confidence_threshold', CONFIDENCE_THRESHOLD)
    if confidence < threshold:
        # mark unanswered for training (existing system handles logging in detect_intent)
        return {'text': random.choice(['I can connect you with a human for help.', 'Would you like me to connect you with support?']), 'confidence': confidence, 'intent_name': intent_name, 'handoff': 'HUMAN'}

    # Route by intent type
    itype = (intent.intent_type or 'info').lower()
    if itype == 'action':
        # find workflows for intent
        wf = intent.workflows.first()
        if wf:
            func_name = wf.function_name
            # call workflow handler dynamically
            func = getattr(workflow_handler, func_name, None)
            if func:
                try:
                    data = func(client_id=client_id, message=message)
                    # prepare template in intent.response if present
                    if intent.response:
                        text = build_response(intent.response, client_id)
                    else:
                        # default render based on returned data
                        text = intent.response or str(data)
                    return {'text': text, 'confidence': confidence, 'intent_name': intent_name, 'data': data}
                except Exception as e:
                    return {'text': 'Sorry, something went wrong while processing your request.', 'confidence': 0.0, 'intent_name': intent_name}
        # no workflow -> fallback
        return {'text': intent.response or 'Action intent configured but no workflow found.', 'confidence': confidence, 'intent_name': intent_name}

    else:
        # info intent -> use configured response or FAQ
        if intent.response:
            text = build_response(intent.response, client_id)
            return {'text': text, 'confidence': confidence, 'intent_name': intent_name}

        # fallback to FAQ search by sector or question match
        # prefer sector-specific FAQ
        if intent.sector:
            faq = FAQ.query.filter_by(sector=intent.sector).first()
        else:
            faq = FAQ.query.filter(FAQ.question.ilike(f"%{intent_name}%")).first()

        if faq:
            return {'text': faq.answer, 'confidence': confidence, 'intent_name': intent_name}

        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}
