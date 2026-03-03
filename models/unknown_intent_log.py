"""
Minimal unknown intent logging for Phase 1.
"""
from database import db
from datetime import datetime


class UnknownIntentLog(db.Model):
    """
    Tracks messages that triggered UNKNOWN fallback.
    Minimal: only what's needed for admin mapping.
    """
    __tablename__ = 'unknown_intent_logs'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
