"""
Chat service for multi-tenant intent-based chatbot
Wraps core intent engine and implements action handlers for LEAD, HUMAN, AUTO intents
"""
from models.chat_log import ChatLog
from database import db
from datetime import datetime
import uuid
from services.intent_service import handle_message as intent_handle_message
from models.usage import Usage
from utils.chat_response import ChatResponse
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def process_message(site_id: int, user_message: str, session_id: str = None, page_url: str = None) -> ChatResponse:
    logging.debug(f"Processing message with site_id={site_id}, user_message={user_message}, session_id={session_id}, page_url={page_url}")

    from models.site import Site
    site_obj = db.session.get(Site, site_id)
    if not site_obj:
        logging.error(f"Site not found for site_id={site_id}")
        return ChatResponse(
            intent_name='ERROR',
            intent_type='ERROR',
            reply='Site not found.',
            confidence=0.0,
            handoff=False,
            lead_capture=False
        )

    if site_obj.status == 'suspended':
        logging.warning(f"Site {site_id} is suspended.")
        return ChatResponse(
            intent_name='SUSPENDED',
            intent_type='ERROR',
            reply='This site is suspended due to usage limits.',
            confidence=0.0,
            handoff=False,
            lead_capture=False
        )

    # Ensure db.session.commit is called only once after all updates
    plan_limit = site_obj.plan.max_monthly_chats if site_obj and site_obj.plan else 1000
    now = datetime.utcnow()
    month_str = now.strftime('%Y-%m')
    logging.debug(f"Plan limit: {plan_limit}, Current month: {month_str}")

    usage = Usage.query.filter_by(site_id=site_id, month=month_str).first()
    if not usage:
        logging.info(f"No usage record found for site_id={site_id}, creating a new one.")
        usage = Usage(site_id=site_id, month=month_str, messages=1)
        db.session.add(usage)
    else:
        usage.messages += 1
        logging.debug(f"Updated usage messages: {usage.messages}")

    if usage.messages >= plan_limit:
        logging.warning(f"Usage limit exceeded for site_id={site_id}. Suspending site.")
        site_obj.status = 'suspended'

    db.session.commit()

    # Use new intent service pipeline (returns dict)
    history = get_session_history(site_id, session_id, limit=10) if session_id else []
    logging.debug(f"Session history: {history}")

    try:
        intent_result = intent_handle_message(user_message, site_id=site_id, history=history, page_url=page_url)
        logging.debug(f"Intent result: {intent_result}")
    except Exception as e:
        logging.error(f"Error in intent_handle_message: {e}")
        raise

    intent_name = intent_result.get('intent_name', 'UNKNOWN')
    intent_type = intent_result.get('intent_type', 'UNKNOWN')
    reply = intent_result.get('text', intent_result.get('response', ''))
    confidence = intent_result.get('confidence', 0.0)

    # Log the chat interaction
    try:
        chat_log = ChatLog(
            site_id=site_id,
            user_message=user_message,
            detected_intent=intent_name,
            confidence=confidence,
            bot_response=reply,
            session_id=session_id,
            created_at=datetime.utcnow()
        )
        db.session.add(chat_log)
        db.session.commit()
        logging.info(f"Chat log saved for site_id={site_id}, session_id={session_id}")
    except Exception as e:
        logging.error(f"Error logging chat: {e}")
        db.session.rollback()

    # Determine response behavior based on intent type
    handoff = False
    lead_capture = False

    if intent_type == 'HUMAN':
        # Trigger handoff to human
        handoff = True
        reply = reply or "Let me connect you with a team member who can help."
    elif intent_type == 'LEAD':
        # Show lead capture form
        lead_capture = True
        reply = reply or "To help you better, may I get your contact information?"
    # AUTO or UNKNOWN: just return reply

    logging.debug(f"Final response: intent_name={intent_name}, intent_type={intent_type}, reply={reply}, confidence={confidence}, handoff={handoff}, lead_capture={lead_capture}")

    return ChatResponse(
        intent_name=intent_name,
        intent_type=intent_type,
        reply=reply,
        confidence=confidence,
        handoff=handoff,
        lead_capture=lead_capture
    )


def get_session_history(site_id: int, session_id: str, limit: int = 10):
    """Retrieve chat history for a session"""
    logs = ChatLog.query.filter_by(
        site_id=site_id,
        session_id=session_id
    ).order_by(ChatLog.created_at.asc()).limit(limit).all()
    
    return [log.to_dict() for log in logs]
