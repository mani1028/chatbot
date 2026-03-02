"""
Chat service for multi-tenant intent-based chatbot
Wraps core intent engine and implements action handlers for LEAD, HUMAN, AUTO intents.

Stage 2 integrations:
- Conversation State Engine (context memory per session)
- Multi-Step Form Engine (step-through data collection)
- Feature Gate checks (plan-based access control)
- Webhook event firing (handoff, lead capture events)
"""
from models.chat_log import ChatLog
from database import db
from datetime import datetime
import uuid
from services.intent_service import handle_message as intent_handle_message
from models.usage import Usage
from utils.chat_response import ChatResponse
import logging

# Stage 2 imports
from models.conversation_state import ConversationState
from services.form_service import get_form_for_intent, start_form, process_form_input
from services.feature_gate import check_feature, FEATURE_AI, FEATURE_FORMS, FEATURE_WEBHOOKS
from services.webhook_service import fire_event, EVENT_HANDOFF, EVENT_LEAD_CAPTURE

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

    # ── Usage Tracking ──────────────────────────────────────────────
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

    # ── Conversation State Engine ───────────────────────────────────
    state = None
    if session_id:
        state = ConversationState.get_or_create(site_id, session_id)

    # ── Check if user is mid-form ───────────────────────────────────
    if state and state.flow_type == 'form' and state.form_id:
        logging.debug(f"Session {session_id} is mid-form (form_id={state.form_id}, step={state.form_step_index})")
        form_result = process_form_input(state, user_message)

        # Log the form interaction
        _log_chat(site_id, session_id, user_message, 
                  f'form_step_{state.form_step_index}', 1.0, form_result.get('text', ''))

        return ChatResponse(
            intent_name=state.active_intent or 'FORM',
            intent_type='FORM',
            reply=form_result.get('text', ''),
            confidence=1.0,
            handoff=False,
            lead_capture=False,
            form_active=form_result.get('form_active', False),
            form_data={k: v for k, v in form_result.items() if k != 'text'}
        )

    # ── Normal intent pipeline ──────────────────────────────────────
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

    # ── Update conversation context ─────────────────────────────────
    if state:
        ctx = state.get_context()
        history_list = ctx.get('intent_history', [])
        history_list.append({
            'intent': intent_name,
            'confidence': confidence,
            'timestamp': now.isoformat()
        })
        state.update_context(
            intent_history=history_list,
            last_intent=intent_name,
            last_confidence=confidence,
            last_message=user_message[:200]
        )
        db.session.commit()

    # ── Check for form trigger ──────────────────────────────────────
    if state and intent_name not in ('UNKNOWN', 'ERROR', 'HUMAN') and confidence >= 0.7:
        if check_feature(site_id, FEATURE_FORMS):
            # Look up if this intent has a linked form
            from models.intent import Intent
            intent_obj = Intent.query.filter_by(site_id=site_id, intent_name=intent_name).first()
            if not intent_obj:
                intent_obj = Intent.query.filter_by(site_id=0, intent_name=intent_name).first()

            if intent_obj:
                form = get_form_for_intent(site_id, intent_obj.id)
                if form:
                    logging.info(f"Starting form '{form.name}' for intent '{intent_name}'")
                    form_result = start_form(state, form)

                    _log_chat(site_id, session_id, user_message, intent_name, confidence,
                              form_result.get('text', ''))

                    # Return the first form question instead of the intent response
                    return ChatResponse(
                        intent_name=intent_name,
                        intent_type='FORM',
                        reply=form_result.get('text', reply),
                        confidence=confidence,
                        handoff=False,
                        lead_capture=False,
                        form_active=form_result.get('form_active', False),
                        form_data={k: v for k, v in form_result.items() if k != 'text'}
                    )

    # ── Log the chat interaction ────────────────────────────────────
    _log_chat(site_id, session_id, user_message, intent_name, confidence, reply)

    # ── Determine response behavior ────────────────────────────────
    handoff = False
    lead_capture = False

    if intent_type == 'HUMAN':
        handoff = True
        reply = reply or "Let me connect you with a team member who can help."
        # Fire webhook for handoff event
        if check_feature(site_id, FEATURE_WEBHOOKS):
            fire_event(site_id, EVENT_HANDOFF, {
                'session_id': session_id,
                'message': user_message,
                'intent': intent_name,
                'page_url': page_url
            })
    elif intent_type == 'LEAD':
        lead_capture = True
        reply = reply or "To help you better, may I get your contact information?"
        if check_feature(site_id, FEATURE_WEBHOOKS):
            fire_event(site_id, EVENT_LEAD_CAPTURE, {
                'session_id': session_id,
                'message': user_message,
                'intent': intent_name
            })

    logging.debug(f"Final response: intent_name={intent_name}, intent_type={intent_type}, reply={reply}, confidence={confidence}, handoff={handoff}, lead_capture={lead_capture}")

    return ChatResponse(
        intent_name=intent_name,
        intent_type=intent_type,
        reply=reply,
        confidence=confidence,
        handoff=handoff,
        lead_capture=lead_capture
    )


def _log_chat(site_id, session_id, user_message, intent_name, confidence, reply):
    """Helper to log a chat interaction."""
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


def get_session_history(site_id: int, session_id: str, limit: int = 10):
    """Retrieve chat history for a session"""
    logs = ChatLog.query.filter_by(
        site_id=site_id,
        session_id=session_id
    ).order_by(ChatLog.created_at.asc()).limit(limit).all()
    
    return [log.to_dict() for log in logs]
