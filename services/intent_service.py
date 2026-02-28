from services.vector_search import query_knowledge_base

from core.intent_engine import detect_intent
from models import Intent
from services.response_builder import build_response
from workflows import handler as workflow_handler
from config import CONFIDENCE_THRESHOLD
import random
import traceback
# LLM fallback
import openai
from models.platform_settings import get_openai_api_key

def llm_fallback(message: str, site_id: int) -> str:
    """Query OpenAI LLM for fallback response."""
    api_key = get_openai_api_key()
    if not api_key:
        return "I'm not sure how to help with that right now."
    openai.api_key = api_key
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant for a business chatbot. Answer concisely and professionally."},
                {"role": "user", "content": message}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return completion.choices[0].message["content"].strip()
    except Exception as e:
        return "I'm not sure how to help with that right now."


def handle_message(message: str, site_id: int, history: list = None, _site_id: int = 0, page_url: str = None) -> dict:
    """Main pipeline entry. Returns a response dict with keys:
       - text
       - intent_name
       - intent_type
       - confidence
       - handoff (optional)
    """
    # 1. Detect Intent
    result = detect_intent(message, site_id, history)
    intent_name = result.get('intent_name')
    confidence = result.get('confidence', 0.0)

    if intent_name in (None, 'UNKNOWN'):
        # RAG knowledge base fallback
        kb_results = query_knowledge_base(site_id, message)
        if kb_results:
            top_score, top_file = kb_results[0]
            if top_score > 0.5:
                return {'text': f"I found this in your knowledge base (file: {top_file.filename}):", 'confidence': top_score, 'intent_name': 'KNOWLEDGE_BASE'}
        # LLM fallback for low confidence
        llm_reply = llm_fallback(message, site_id)
        return {'text': llm_reply, 'confidence': confidence, 'intent_name': 'UNKNOWN'}

    # 2. Fetch Intent from DB
    intent = Intent.query.filter((Intent.site_id == site_id) | (Intent.site_id == 0)).filter_by(intent_name=intent_name).first()

    if not intent:
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}

    # 3. Check Confidence
    threshold = getattr(intent, 'confidence_threshold', CONFIDENCE_THRESHOLD)
    itype = (intent.intent_type or 'info').lower()
    # Only handoff if confidence is extremely low, or intent is unknown
    if confidence < 0.3 or intent_name == 'UNKNOWN':
        return {
            'text': "I'm not quite sure, but I can connect you with a human.",
            'confidence': confidence,
            'intent_name': intent_name,
            'handoff': 'HUMAN'
        }

    # 4. Handle Intent Types
    itype = (intent.intent_type or 'info').lower()
    
    if itype == 'action':
        wf = intent.workflows.first()
        if wf:
            func_name = wf.function_name
            func = getattr(workflow_handler, func_name, None)
            if func:
                try:
                    # Pass order_id if present in message or kwargs for ERP integration
                    if func_name == 'track_order':
                        # Extract order_id from message or context (customize as needed)
                        order_id = None
                        if isinstance(message, str):
                            # Simple extraction: look for 'order' followed by digits
                            import re
                            match = re.search(r'order\s*(\d+)', message)
                            if match:
                                order_id = match.group(1)
                        data = func(site_id=site_id, order_id=order_id, message=message)
                    else:
                        data = func(site_id=site_id, message=message)
                    text = build_response(intent.response, site_id) if intent.response else str(data)
                    return {'text': text, 'confidence': confidence, 'intent_name': intent_name, 'data': data}
                except Exception as e:
                    print(f"\u274c WORKFLOW ERROR ({func_name}): {str(e)}")
                    traceback.print_exc()
                    return {'text': 'Sorry, something went wrong while processing your request.', 'confidence': 0.0, 'intent_name': intent_name}
        return {'text': intent.response or 'Action intent configured but no workflow found.', 'confidence': confidence, 'intent_name': intent_name}
    else:
        # Info Intent Logic
        if intent.response:
            text = build_response(intent.response, site_id)
            return {'text': text, 'confidence': confidence, 'intent_name': intent_name}
        return {'text': result.get('response'), 'confidence': confidence, 'intent_name': intent_name}