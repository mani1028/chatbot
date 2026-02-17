from database import db
from datetime import datetime


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