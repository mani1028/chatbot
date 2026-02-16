from models.site import Site
from models.platform_settings import PlatformSetting
from database import db
from datetime import datetime
import uuid

class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(255), nullable=True)
    user_message = db.Column(db.Text, nullable=False)
    detected_intent = db.Column(db.String(255), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    bot_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'session_id': self.session_id,
            'user_message': self.user_message,
            'detected_intent': self.detected_intent,
            'confidence': self.confidence,
            'bot_response': self.bot_response,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ChatResponse:
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
    from services.intent_service import handle_message as intent_handle_message
    
    settings = PlatformSetting.query.first()
    if settings and settings.maintenance_mode:
        return ChatResponse("SYSTEM", "INFO", "System is currently under maintenance. Please try again later.", 1.0)

    site = db.session.get(Site, site_id)
    if not site or not site.is_active:
        return ChatResponse("SYSTEM", "INFO", "This chatbot is currently inactive.", 1.0)

    if site.plan:
        if site.message_count >= site.plan.message_limit:
            return ChatResponse("SYSTEM", "INFO", "Monthly message limit reached. Please contact support.", 1.0)

    if not session_id:
        session_id = str(uuid.uuid4())
    
    intent_result = intent_handle_message(user_message, client_id=site_id, site_id=site_id)

    intent_name = intent_result.get('intent_name', 'UNKNOWN')
    intent_type = intent_result.get('intent_type', 'UNKNOWN')
    reply = intent_result.get('text', intent_result.get('response', ''))
    confidence = intent_result.get('confidence', 0.0)
    
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
        site.message_count += 1
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    
    handoff = (intent_type == 'HUMAN')
    lead_capture = (intent_type == 'LEAD')
    
    if handoff: reply = reply or "Let me connect you with a team member."
    if lead_capture: reply = reply or "Can I get your contact details?"
    
    return ChatResponse(intent_name, intent_type, reply, confidence, handoff, lead_capture)

def get_session_history(site_id: int, session_id: str, limit: int = 10):
    logs = ChatLog.query.filter_by(site_id=site_id, session_id=session_id)\
        .order_by(ChatLog.created_at.asc()).limit(limit).all()
    return [log.to_dict() for log in logs]