from database import db
from datetime import datetime

class LeadCapture(db.Model):
    __tablename__ = 'lead_captures'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=True)  # NEW: Track which site captured this lead
    session_id = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    user_phone = db.Column(db.String(50), nullable=True)
    question_context = db.Column(db.Text, nullable=True)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
