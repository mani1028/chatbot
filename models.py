"""
Database models for chatbot application
"""
from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(db.Model):
    """
    Admin user model for authentication
    """
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Admin {self.username}>'


class FAQ(db.Model):
    """
    FAQ model - stores question-answer pairs
    """
    __tablename__ = 'faqs'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False, unique=True)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert FAQ to dictionary"""
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'category': self.category,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<FAQ {self.question[:50]}>'


class ChatLog(db.Model):
    """
    Chat log model - stores all user messages and bot responses
    """
    __tablename__ = 'chat_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    matched_faq_id = db.Column(db.Integer, db.ForeignKey('faqs.id'), nullable=True)
    session_id = db.Column(db.String(100), nullable=False)  # To group conversations
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    faq = db.relationship('FAQ', backref='chat_logs')
    
    def to_dict(self):
        """Convert ChatLog to dictionary"""
        return {
            'id': self.id,
            'user_message': self.user_message,
            'bot_response': self.bot_response,
            'confidence_score': round(self.confidence_score, 2),
            'matched_faq_id': self.matched_faq_id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'is_answered': self.matched_faq_id is not None
        }
    
    def __repr__(self):
        return f'<ChatLog {self.user_message[:30]}>'


class UnansweredQuestion(db.Model):
    """
    Unanswered question model - tracks questions bot couldn't answer
    """
    __tablename__ = 'unanswered_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    times_asked = db.Column(db.Integer, default=1)
    last_asked = db.Column(db.DateTime, default=datetime.utcnow)
    first_asked = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'question': self.question,
            'times_asked': self.times_asked,
            'first_asked': self.first_asked.isoformat(),
            'last_asked': self.last_asked.isoformat()
        }
    
    def __repr__(self):
        return f'<UnansweredQuestion {self.question[:50]}>'
