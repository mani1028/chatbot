from database import db
from datetime import datetime

class UnansweredQuestion(db.Model):
    __tablename__ = 'unanswered_questions'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    times_asked = db.Column(db.Integer, default=1)
    last_asked = db.Column(db.DateTime, default=datetime.utcnow)
    first_asked = db.Column(db.DateTime, default=datetime.utcnow)
    user_name = db.Column(db.String(255), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='pending')
    contacted_at = db.Column(db.DateTime, nullable=True)
