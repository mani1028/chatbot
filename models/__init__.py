"""
Database models package for chatbot application
Updated for Multi-Tenancy Branding
"""
from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(db.Model):
    """Admin user model for authentication"""
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_super = db.Column(db.Boolean, default=False)
    site_id = db.Column(db.Integer, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Admin {self.username}>'

class FAQ(db.Model):
    """FAQ model - stores question-answer pairs"""
    __tablename__ = 'faqs'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False, unique=True)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'category': self.category,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class UnansweredQuestion(db.Model):
    """Tracks questions bot couldn't answer"""
    __tablename__ = 'unanswered_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    times_asked = db.Column(db.Integer, default=1)
    last_asked = db.Column(db.DateTime, default=datetime.utcnow)
    first_asked = db.Column(db.DateTime, default=datetime.utcnow)
    user_name = db.Column(db.String(255), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='pending')
    contacted_at = db.Column(db.DateTime, nullable=True)

class LeadCapture(db.Model):
    """Lead capture model"""
    __tablename__ = 'lead_captures'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    question_context = db.Column(db.Text, nullable=True)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)

class BrandingSettings(db.Model):
    """
    Branding configuration model - stores widget customization
    NOW MULTI-TENANT with site_id
    """
    __tablename__ = 'branding_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    # Vital for Multi-Tenancy:
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False, default=1) 
    
    bot_name = db.Column(db.String(255), default='ChatBot')
    bot_description = db.Column(db.String(500), default="We're here to help")
    
    # Visuals
    primary_color = db.Column(db.String(7), default='#667eea')
    secondary_color = db.Column(db.String(7), default='#764ba2')
    accent_color = db.Column(db.String(7), default='#4CAF50')
    
    # Assets
    logo_url = db.Column(db.String(500), nullable=True)
    favicon_url = db.Column(db.String(500), nullable=True)
    
    # Behavior
    initial_message = db.Column(db.Text, default="Hi! 👋 How can I help you today?")
    position = db.Column(db.String(20), default='bottom-right')
    theme_mode = db.Column(db.String(10), default='light')
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'bot_name': self.bot_name,
            'bot_description': self.bot_description,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color': self.accent_color,
            'logo_url': self.logo_url,
            'favicon_url': self.favicon_url,
            'initial_message': self.initial_message,
            'position': self.position,
            'theme_mode': self.theme_mode
        }

# Import new models from package siblings
from .site import Site  # noqa: F401
from .intent import Intent, IntentPhrase, Workflow, ClientConfig  # noqa: F401
from .chat_log import ChatLog  # noqa: F401