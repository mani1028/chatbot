"""
Multi-tenant chat log model for storing conversations per site
"""
from database import db
from datetime import datetime


class ChatLog(db.Model):
    """Multi-tenant chat log with site_id scoping"""
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    detected_intent = db.Column(db.String(255), nullable=True)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    bot_response = db.Column(db.Text, nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'user_message': self.user_message,
            'detected_intent': self.detected_intent,
            'confidence': round(self.confidence, 3),
            'bot_response': self.bot_response,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'is_answered': self.detected_intent != 'UNKNOWN'
        }

    def __repr__(self):
        return f'<ChatLog site={self.site_id} {self.user_message[:30]}>'
