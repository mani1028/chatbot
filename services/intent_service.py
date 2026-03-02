import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    import os
    import time
    
    api_key = get_openai_api_key()
    if not api_key:
        logging.warning(f"LLM Fallback [site_id={site_id}]: No OpenAI API key found")
        return "I'm not sure how to help with that right now. Please try rephrasing."
    
    # Validate API key format
    if not isinstance(api_key, str):
        logging.error(f"LLM Fallback [site_id={site_id}]: API key is not a string")
        return "I'm not sure how to help with that right now."
        
    if not api_key.startswith('sk-'):
        logging.error(f"LLM Fallback [site_id={site_id}]: Invalid API key format. Starts with: {api_key[:10] if len(api_key) > 10 else api_key}")
        return "I'm not sure how to help with that right now."

    try:
        from openai import OpenAI
        logging.debug(f"LLM Fallback [site_id={site_id}]: Initializing OpenAI client")
        client = OpenAI(api_key=api_key, timeout=15)
        
        logging.info(f"LLM Fallback [site_id={site_id}]: Calling GPT-4o-mini with: {message[:80]}...")
        
        start_time = time.time()
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant for a business chatbot. Answer concisely and professionally in 1-2 sentences."},
                {"role": "user", "content": message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        elapsed = time.time() - start_time
        response = completion.choices[0].message.content.strip()
        logging.info(f"LLM Fallback [site_id={site_id}]: Success in {elapsed:.2f}s. Response: {response[:100]}...")
        return response
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logging.error(f"LLM Fallback [site_id={site_id}]: API Error [{error_type}]: {error_msg}")
        
        # Provide specific error info
        if "authentication" in error_msg.lower() or "invalid_api_key" in error_msg.lower():
            logging.error(f"LLM Fallback [site_id={site_id}]: Check your OpenAI API key validity")
        elif "rate_limit" in error_msg.lower():
            logging.warning(f"LLM Fallback [site_id={site_id}]: Rate limited - will retry")
        elif "timeout" in error_msg.lower():
            logging.warning(f"LLM Fallback [site_id={site_id}]: Request timeout")
            
        import traceback
        logging.debug(f"LLM Fallback Traceback:\n{traceback.format_exc()}")
        return "I'm not sure how to help with that right now. Please try rephrasing."


def handle_message(message: str, site_id: int, history: list = None, _site_id: int = 0, page_url: str = None) -> dict:
    """Main pipeline entry. Returns a response dict with keys:
       - text
       - intent_name
       - intent_type
       - confidence
       - handoff (optional)
    """
    logging.debug(f"Handling message: message={message}, site_id={site_id}, history={history}, page_url={page_url}")

    # Validate input
    if not message or not isinstance(message, str):
        logging.error("Invalid or missing 'message' parameter.")
        return {
            'text': "Sorry, I couldn't understand your request.",
            'confidence': 0.0,
            'intent_name': 'ERROR',
            'intent_type': 'ERROR'
        }

    try:
        # 1. Detect Intent
        result = detect_intent(message, site_id, history)
        logging.debug(f"Intent detection result: {result}")
        intent_name = result.get('intent_name')
        confidence = result.get('confidence', 0.0)

        if intent_name in (None, 'UNKNOWN'):
            # RAG knowledge base fallback
            kb_results = query_knowledge_base(site_id, message)
            logging.debug(f"Knowledge base results: {kb_results}")
            if kb_results:
                top_score, top_file = kb_results[0]
                if top_score > 0.5:
                    return {'text': f"I found this in your knowledge base (file: {top_file.filename}):", 'confidence': top_score, 'intent_name': 'KNOWLEDGE_BASE'}
            # LLM fallback for low confidence
            llm_reply = llm_fallback(message, site_id)
            return {'text': llm_reply, 'confidence': confidence, 'intent_name': 'UNKNOWN'}

        # 2. Fetch Intent from DB
        intent = Intent.query.filter((Intent.site_id == site_id) | (Intent.site_id == 0)).filter_by(intent_name=intent_name).first()
        logging.debug(f"Fetched intent: {intent}")

        if not intent:
            return {
                'text': result.get('response'), 
                'confidence': confidence, 
                'intent_name': intent_name,
                'intent_type': result.get('intent_type'),
                'handoff': result.get('handoff')
            }

        # 3. Check Confidence
        threshold = getattr(intent, 'confidence_threshold', CONFIDENCE_THRESHOLD)
        itype = (intent.intent_type or 'info').lower()
        if confidence < 0.3 or intent_name == 'UNKNOWN':
            # Rely on your LLM fallback for low confidence queries
            llm_reply = llm_fallback(message, site_id)
            return {
                'text': llm_reply,
                'confidence': confidence,
                'intent_name': 'LLM_FALLBACK',
                'handoff': None
            }

        # 4. Handle Intent Types
        itype = (intent.intent_type or 'info').lower()

        # --- NEW: LIVE AGENT FALLBACK LOGIC ---
        if itype == 'human' or result.get('handoff') == 'HUMAN':
            from models.client_config import ClientConfig
            # Check if this specific client has live agents enabled
            live_agent_config = ClientConfig.query.filter_by(site_id=site_id, key='live_agents_enabled').first()

            if not live_agent_config or live_agent_config.value != 'true':
                # Force override to a Lead form!
                return {
                    'text': "Our live support team is currently offline, but we'd love to help! Please describe your issue below and we will contact you shortly:",
                    'confidence': confidence,
                    'intent_name': intent_name,
                    'intent_type': 'LEAD',
                    'handoff': 'LEAD'
                }
            else:
                # Proceed with standard human handoff
                return {
                    'text': intent.response or "Connecting you to a human agent...",
                    'confidence': confidence,
                    'intent_name': intent_name,
                    'intent_type': 'HUMAN',
                    'handoff': 'HUMAN'
                }
        # ---------------------------------------

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
                        return {
                            'text': text, 
                            'confidence': confidence, 
                            'intent_name': intent_name, 
                            'data': data,
                            'intent_type': itype.upper()
                        }
                    except Exception as e:
                        logging.error(f"Workflow error in {func_name}: {e}")
                        return {'text': 'Sorry, something went wrong while processing your request.', 'confidence': 0.0, 'intent_name': intent_name}
            return {'text': intent.response or 'Action intent configured but no workflow found.', 'confidence': confidence, 'intent_name': intent_name}
        else:
            # Info Intent Logic (and LEAD forms)
            text = build_response(intent.response, site_id) if intent.response else result.get('response')
            return {
                'text': text, 
                'confidence': confidence, 
                'intent_name': intent_name,
                'intent_type': itype.upper(),
                'handoff': result.get('handoff') or (itype.upper() if itype.upper() in ['LEAD', 'HUMAN'] else None)
            }

    except Exception as e:
        logging.error(f"Error in handle_message: {e}")
        logging.debug(f"Message: {message}, Site ID: {site_id}, History: {history}, Page URL: {page_url}")
        logging.debug(f"Traceback: {traceback.format_exc()}")
        return {
            'text': 'An error occurred while processing your request.',
            'confidence': 0.0,
            'intent_name': 'ERROR',
            'intent_type': 'ERROR'
        }