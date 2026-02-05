"""
Database models for chatbot application
"""
from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

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


class Intent(db.Model):
    """
    Intent model - stores intent definitions with training phrases
    Replaces the old FAQ model for intent-based matching
    """
    __tablename__ = 'intents'
    
    id = db.Column(db.Integer, primary_key=True)
    intent_name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(100), default='General')
    training_phrases = db.Column(db.Text, nullable=False)  # JSON array of phrases
    short_response = db.Column(db.Text, nullable=False)
    detailed_response = db.Column(db.Text, nullable=False)
    requires_handoff = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_training_phrases(self):
        """Get training phrases as list"""
        try:
            return json.loads(self.training_phrases)
        except:
            return []
    
    def set_training_phrases(self, phrases):
        """Set training phrases from list"""
        self.training_phrases = json.dumps(phrases)
    
    def to_dict(self):
        """Convert Intent to dictionary"""
        return {
            'id': self.id,
            'intent_name': self.intent_name,
            'category': self.category,
            'training_phrases': self.get_training_phrases(),
            'short_response': self.short_response,
            'detailed_response': self.detailed_response,
            'requires_handoff': self.requires_handoff,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Intent {self.intent_name}>'


class FAQ(db.Model):
    """
    FAQ model - stores question-answer pairs (legacy, kept for backward compatibility)
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
    matched_intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=True)
    matched_faq_id = db.Column(db.Integer, db.ForeignKey('faqs.id'), nullable=True)
    message_type = db.Column(db.String(50), default='auto_response')  # auto_response, lead_capture, handoff
    session_id = db.Column(db.String(100), nullable=False)  # To group conversations
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    intent = db.relationship('Intent', backref='chat_logs')
    faq = db.relationship('FAQ', backref='chat_logs')
    
    def to_dict(self):
        """Convert ChatLog to dictionary"""
        return {
            'id': self.id,
            'user_message': self.user_message,
            'bot_response': self.bot_response,
            'confidence_score': round(self.confidence_score, 2),
            'matched_intent_id': self.matched_intent_id,
            'matched_faq_id': self.matched_faq_id,
            'message_type': self.message_type,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat(),
            'is_answered': self.matched_intent_id is not None or self.matched_faq_id is not None
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


class Lead(db.Model):
    """
    Lead model - stores information about users who need human handoff
    """
    __tablename__ = 'leads'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    message = db.Column(db.Text, nullable=False)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=True)
    session_id = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='new')  # new, assigned, resolved
    assigned_to = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    intent = db.relationship('Intent', backref='leads')
    
    def to_dict(self):
        """Convert Lead to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'message': self.message,
            'intent_id': self.intent_id,
            'session_id': self.session_id,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Lead {self.email}>'
