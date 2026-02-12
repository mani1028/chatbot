"""
Chat service for multi-tenant intent-based chatbot
Wraps core intent engine and implements action handlers for LEAD, HUMAN, AUTO intents
"""
from models.chat_log import ChatLog
from database import db
from datetime import datetime
import uuid
from services.intent_service import handle_message as intent_handle_message


class ChatResponse:
    """Standardized chat response object"""
    def __init__(self, intent_name, intent_type, reply, confidence, handoff=False, lead_capture=False):
        self.intent_name = intent_name
        self.intent_type = intent_type
        self.reply = reply
        self.confidence = confidence
        self.handoff = handoff
        self.lead_capture = lead_capture

    def to_dict(self):
        return {
            'reply': self.reply,
            'intent': self.intent_name,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'handoff': self.handoff,
            'lead_capture': self.lead_capture
        }


def process_message(site_id: int, user_message: str, session_id: str = None) -> ChatResponse:
    """
    Process user message for a given site.
    
    Flow:
    1. Detect intent using core engine
    2. Log the interaction
    3. Handle intent type (AUTO -> reply, LEAD -> capture form, HUMAN -> handoff)
    
    Returns: ChatResponse object
    """
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Use new intent service pipeline (returns dict)
    intent_result = intent_handle_message(user_message, client_id=site_id, site_id=site_id)

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
    except Exception as e:
        print(f"Error logging chat: {e}")
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
