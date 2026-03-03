"""
Chat service for multi-tenant intent-based chatbot
Wraps MessageOrchestrator (Phase 2 kernel) with adapter layer for backward compatibility.

Architecture:
- MessageOrchestrator: 10-stage deterministic pipeline (truth)
- Adapter: Converts orchestrator output to legacy ChatResponse schema (compatibility)
- Frontend (widget.js): Receives legacy format, no changes needed
"""
from models.chat_log import ChatLog
from database import db
from datetime import datetime
import uuid
from models.usage import Usage
from utils.chat_response import ChatResponse
import logging

# Orchestrator imports (Phase 2 kernel)
from services.message_orchestrator import get_message_orchestrator

# Feature gate (still needed for webhooks)
from services.feature_gate import check_feature, FEATURE_WEBHOOKS
from services.webhook_service import fire_event, EVENT_HANDOFF, EVENT_LEAD_CAPTURE

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def _adapt_orchestrator_response(orchestrator_result: dict) -> ChatResponse:
    """
    Adapter layer: Converts orchestrator output to legacy ChatResponse schema.
    
    Orchestrator returns structured intent data.
    Widget.js expects legacy field names.
    
    No parsing. No hacks. Just mapping.
    """
    # Extract orchestrator data
    reply = orchestrator_result.get("reply", "")
    intent_name = orchestrator_result.get("intent_name")
    intent_confidence = orchestrator_result.get("intent_confidence", 0.0)
    workflow_state = orchestrator_result.get("workflow_state")
    workflow_type = orchestrator_result.get("workflow_type")
    collected_data = orchestrator_result.get("collected_data", {})
    context = orchestrator_result.get("context_analysis", {})
    
    # Determine intent_type based on workflow or escalation
    intent_type = "INFO"  # Default
    handoff = context.get("should_escalate", False)
    
    # Detect if this is a lead capture scenario
    lead_capture = False
    if intent_name and any(keyword in intent_name.lower() for keyword in ['lead', 'inquiry', 'signup']):
        lead_capture = True
        intent_type = "LEAD"
    
    # Detect if this is a handoff scenario
    if handoff:
        intent_type = "HUMAN"
    
    # Build legacy response
    return ChatResponse(
        intent_name=intent_name or "UNKNOWN",
        intent_type=intent_type,
        reply=reply,
        confidence=intent_confidence,
        handoff=handoff,
        lead_capture=lead_capture,
        workflow_state=workflow_state,
        collected_data=collected_data
    )


def process_message(site_id: int, user_message: str, session_id: str = None, page_url: str = None) -> ChatResponse:
    """
    Process user message through orchestrator with backward-compatible response.
    
    Takes legacy parameters, uses orchestrator internally, returns legacy schema.
    """
    logging.debug(f"Processing message: site_id={site_id}, session_id={session_id}, len={len(user_message)}")

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
        logging.info(f"No usage record found for site_id={site_id}, creating new one.")
        usage = Usage(site_id=site_id, month=month_str, messages=1)
        db.session.add(usage)
    else:
        usage.messages += 1
        logging.debug(f"Updated usage messages: {usage.messages}")

    if usage.messages >= plan_limit:
        logging.warning(f"Usage limit exceeded for site_id={site_id}. Suspending site.")
        site_obj.status = 'suspended'

    db.session.commit()

    # ── Call Orchestrator ───────────────────────────────────────────
    # This is the single execution kernel.
    # It handles all state management, workflows, intent detection, LLM fallback.
    orchestrator = get_message_orchestrator()
    
    try:
        orchestrator_result = orchestrator.process_message(
            site_id=str(site_id),
            session_id=session_id or str(uuid.uuid4()),
            message=user_message
        )
        logging.debug(f"Orchestrator result: intent={orchestrator_result.get('intent_name')}, " +
                     f"confidence={orchestrator_result.get('intent_confidence')}")
    except Exception as e:
        # CRITICAL: Re-raise database errors to prevent state divergence
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(e, SQLAlchemyError):
            logging.error(f"DATABASE ERROR - Must propagate: {e}", exc_info=True)
            raise  # Let route return 500
        
        logging.error(f"Orchestrator error: {e}", exc_info=True)
        return ChatResponse(
            intent_name='ERROR',
            intent_type='ERROR',
            reply='⚠️ An error occurred processing your message.',
            confidence=0.0,
            handoff=False,
            lead_capture=False
        )

    # ── Adapt to Legacy Schema ──────────────────────────────────────
    # Frontend expects: intent_name, intent_type, handoff, lead_capture
    # Orchestrator provides: intent_name, intent_confidence, context_analysis
    response = _adapt_orchestrator_response(orchestrator_result)
    
    # DEBUG: Show what orchestrator returned vs what adapter produced
    print("=" * 60)
    print("=== ORCHESTRATOR RAW ===")
    print(f"  intent_name: {orchestrator_result.get('intent_name')}")
    print(f"  intent_confidence: {orchestrator_result.get('intent_confidence')}")
    print(f"  reply: {orchestrator_result.get('reply')[:50]}...")
    print(f"  workflow_state: {orchestrator_result.get('workflow_state')}")
    print(f"  should_escalate: {orchestrator_result.get('context_analysis', {}).get('should_escalate')}")
    print("=== LEGACY RESPONSE ===")
    print(f"  intent_name: {response.intent_name}")
    print(f"  intent_type: {response.intent_type}")
    print(f"  confidence: {response.confidence}")
    print(f"  handoff: {response.handoff}")
    print(f"  lead_capture: {response.lead_capture}")
    print(f"  reply: {response.reply[:50]}...")
    print("=" * 60)
    
    # ── Fire Webhooks (if enabled) ──────────────────────────────────
    if check_feature(site_id, FEATURE_WEBHOOKS):
        if response.handoff:
            fire_event(site_id, EVENT_HANDOFF, {
                'session_id': session_id,
                'message': user_message,
                'intent': response.intent_name,
                'page_url': page_url
            })
        elif response.lead_capture:
            fire_event(site_id, EVENT_LEAD_CAPTURE, {
                'session_id': session_id,
                'message': user_message,
                'intent': response.intent_name
            })

    # ── Log Chat (backward compatibility) ────────────────────────────
    _log_chat(site_id, session_id, user_message, 
              response.intent_name, response.confidence, response.reply)

    return response


def _log_chat(site_id, session_id, user_message, intent_name, confidence, reply):
    """Helper to log a chat interaction."""
    # Check the per-site setting for preserving chat history
    from models.client_config import ClientConfig
    preserve_chat_history = ClientConfig.query.filter_by(
        site_id=site_id, 
        key='preserve_chat_history'
    ).first()
    
    # If preserve_chat_history is "off", don't log messages
    if preserve_chat_history and preserve_chat_history.value == 'off':
        logging.debug(f"Chat history preservation is disabled for site_id={site_id}")
        return
    
    # If the setting doesn't exist or is "on", log the chat
    try:
        chat_log = ChatLog(
            site_id=site_id,
            session_id=session_id,
            user_message=user_message,
            detected_intent=intent_name,
            confidence=confidence,
            bot_response=reply
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
