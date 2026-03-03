import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

from services.vector_search import query_knowledge_base

from core.intent_engine import detect_intent
from models import Intent
from services.response_builder import build_response
from workflows import handler as workflow_handler
from config import CONFIDENCE_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD, ACTION_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD
import random
import traceback
import requests
# LLM fallback
from models.platform_settings import get_openai_api_key

def llm_fallback(message: str, site_id: int) -> str:
    """Query LLM for fallback response with hard timeout protection.
    
    Enforces:
    - 3s connection timeout (fail fast on network issues)
    - 12s read timeout (total response maximum ~15s)
    - 15s application-level max wall-clock time
    
    This protects Gunicorn workers from blocking indefinitely.
    """
    import os
    import time
    
    api_key = get_openai_api_key()
    if not api_key:
        logging.warning(f"LLM Fallback [site_id={site_id}]: No API key found")
        return "I'm not sure how to help with that right now. Please try rephrasing."
    
    # Validate API key format
    if not isinstance(api_key, str):
        logging.error(f"LLM Fallback [site_id={site_id}]: API key is not a string")
        return "I'm not sure how to help with that right now."
    
    # Determine which API to use based on key format
    is_openrouter = api_key.startswith('sk-or-')
    is_openai = api_key.startswith('sk-')
    
    if not (is_openrouter or is_openai):
        logging.error(f"LLM Fallback [site_id={site_id}]: Invalid API key format. Starts with: {api_key[:15] if len(api_key) > 15 else api_key}")
        return "I'm not sure how to help with that right now."

    try:
        start_time = time.time()
        
        if is_openrouter:
            # Use OpenRouter API
            logging.info(f"LLM Fallback [site_id={site_id}]: Using OpenRouter API with message: {message[:80]}...")
            
            # Timeout: (connect_timeout=3s, read_timeout=12s)
            # This protects workers from blocking > 15s on single request
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "Chatbot",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful AI assistant for a business chatbot. Answer concisely and professionally in 1-2 sentences."},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 150,
                    "temperature": 0.7
                },
                timeout=(3, 12)
            )
            
            if response.status_code != 200:
                error_msg = response.text
                logging.error(f"LLM Fallback [site_id={site_id}]: OpenRouter API error: {response.status_code} - {error_msg}")
                return "I'm not sure how to help with that right now. Please try rephrasing."
            
            result = response.json()
            llm_response = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
        else:
            # Use OpenAI API directly
            logging.info(f"LLM Fallback [site_id={site_id}]: Using OpenAI API with message: {message[:80]}...")
            
            from openai import OpenAI
            # Timeout: (connect_timeout=3s, read_timeout=12s)
            client = OpenAI(api_key=api_key, timeout=(3, 12))
            
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant for a business chatbot. Answer concisely and professionally in 1-2 sentences."},
                    {"role": "user", "content": message}
                ],
                max_tokens=150,
                temperature=0.7
            )
            llm_response = completion.choices[0].message.content.strip()
        
        elapsed = time.time() - start_time
        
        # Application-level max execution time guard
        if elapsed > 15:
            logging.warning(f"LLM Fallback [site_id={site_id}]: Exceeded 15s wall-clock time ({elapsed:.2f}s), returning fallback to protect worker")
            return "I'm not sure how to help with that right now. Please try rephrasing."
        
        logging.info(f"LLM Fallback [site_id={site_id}]: Success in {elapsed:.2f}s. Response: {llm_response[:100]}...")
        return llm_response
        
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        elapsed = time.time() - start_time
        
        # Log timeout events separately (critical for production observability)
        if "timeout" in error_msg.lower():
            logging.warning(f"LLM Fallback [site_id={site_id}]: Request timeout after {elapsed:.2f}s [{error_type}]. Worker protected.")
        else:
            logging.error(f"LLM Fallback [site_id={site_id}]: API Error [{error_type}] after {elapsed:.2f}s: {error_msg}")
        
        # Provide specific error context
        if "authentication" in error_msg.lower() or "invalid_api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
            logging.error(f"LLM Fallback [site_id={site_id}]: Check your API key configuration")
        elif "rate_limit" in error_msg.lower():
            logging.warning(f"LLM Fallback [site_id={site_id}]: Rate limited by LLM provider")
            
        logging.debug(f"LLM Fallback Traceback:\n{traceback.format_exc()}")
        return "I'm not sure how to help with that right now. Please try rephrasing."


def apply_context_awareness(intent_result: dict, message: str, history: list = None) -> dict:
    """
    Context-aware intent resolution.
    Enhances intent detection by considering conversation history and patterns.
    
    Returns the possibly enhanced intent_result dict.
    """
    if not history:
        return intent_result
    
    intent_name = intent_result.get('intent_name', 'UNKNOWN')
    confidence = intent_result.get('confidence', 0.0)
    
    # Pattern 1: If previous intents show a pattern, increase confidence for consistent intents
    recent_intents = [h.get('detected_intent') for h in history[-3:]]
    if recent_intents and intent_name in recent_intents:
        # This intent appears in recent history - likely a follow-up
        confidence = min(1.0, confidence + 0.15)
        logging.debug(f"Context boost [pattern follow-up]: {intent_name} confidence -> {confidence}")
    
    # Pattern 2: If many UNKNOWN intents, escalate more aggressively to support
    unknown_count = sum(1 for h in history if h.get('detected_intent') == 'UNKNOWN')
    if unknown_count >= 3 and intent_name == 'UNKNOWN':
        # User has asked 3+ unrecognized questions - suggest support
        logging.debug(f"Context escalation [repeated unknowns]: User may need support")
        intent_result['suggest_support'] = True
    
    # Pattern 3: Detect booking follow-ups
    if any(keyword in message.lower() for keyword in ['when', 'time', 'date', 'confirm', 'appointment']):
        # Check if user recently asked about booking
        for h in history[-5:]:
            if any(kw in str(h.get('user_message', '')).lower() for kw in ['book', 'appointment', 'schedule']):
                if intent_name == 'UNKNOWN':
                    intent_name = 'BOOKING_FOLLOWUP'
                    confidence = 0.8
                    logging.debug(f"Context detection [booking follow-up]: Inferred intent from history")
                    intent_result['intent_name'] = intent_name
                    intent_result['confidence'] = confidence
                break
    
    # Pattern 4: Detect sentiment escalation
    escalation_keywords = ['urgent', 'asap', 'immediately', 'help', 'emergency', 'critical']
    if any(keyword in message.lower() for keyword in escalation_keywords):
        if confidence < CONFIDENCE_THRESHOLD:
            # Low confidence + urgent language = escalate to support
            intent_name = 'SUPPORT_ESCALATION'
            confidence = HIGH_CONFIDENCE_THRESHOLD
            logging.debug(f"Context detection [urgent escalation]: Detected escalation keywords")
            intent_result['intent_name'] = intent_name
            intent_result['confidence'] = confidence
    
    # Update the result with enhanced confidence
    intent_result['confidence'] = confidence
    
    return intent_result


def detect_intent_only(message: str, site_id: int, history: list = None) -> dict:
    """
    Pure intent detection WITHOUT LLM fallback.
    
    This is used by orchestrator to detect intent and let orchestrator own LLM invocation.
    
    Args:
        message: User message
        site_id: Site ID
        history: Conversation history (optional)
    
    Returns:
        {
            'intent_name': str or 'UNKNOWN',
            'intent_type': str,
            'confidence': float (0-1),
            'response': str,
            'handoff': str or None
        }
    """
    if not message or not isinstance(message, str):
        return {
            'intent_name': 'ERROR',
            'intent_type': 'ERROR',
            'confidence': 0.0,
            'response': "Invalid message"
        }
    
    try:
        # 1. Detect Intent (no LLM)
        result = detect_intent(message, site_id, history)
        logging.debug(f"[INTENT CORE] Detection: {result.get('intent_name')} @ {result.get('confidence')}")
        
        # 2. Apply context-aware enhancements
        result = apply_context_awareness(result, message, history)
        
        # NOTE: DO NOT CALL LLM HERE
        # That is orchestrator's responsibility
        
        return result
        
    except Exception as e:
        logging.error(f"Error in detect_intent_only: {e}")
        return {
            'intent_name': 'UNKNOWN',
            'intent_type': 'UNKNOWN',
            'confidence': 0.0,
            'response': "Error detecting intent"
        }


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
        
        # 2. Apply context-aware enhancements
        result = apply_context_awareness(result, message, history)
        logging.debug(f"Context-aware intent result: {result}")
        
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
            # Signal orchestrator to handle LLM invocation (no LLM call here)
            return {'text': '', 'confidence': confidence, 'intent_name': 'UNKNOWN', 'requires_llm': True}

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
        if confidence < ACTION_CONFIDENCE_THRESHOLD or intent_name == 'UNKNOWN':
            # Signal orchestrator to handle LLM invocation (no LLM call here)
            return {
                'text': '',
                'confidence': confidence,
                'intent_name': 'UNKNOWN',
                'requires_llm': True,
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