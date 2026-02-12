"""
Database models package for chatbot application
Moved from top-level models.py to package for multi-tenant refactor
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
    # Link admin to a specific site (Tenant). Null for Super Admins.
    site_id = db.Column(db.Integer, nullable=True) 
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
    """FAQ model - stores question-answer pairs (Legacy/Optional)"""
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

class UnansweredQuestion(db.Model):
    """Unanswered question model - tracks questions bot couldn't answer"""
    __tablename__ = 'unanswered_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    times_asked = db.Column(db.Integer, default=1)
    last_asked = db.Column(db.DateTime, default=datetime.utcnow)
    first_asked = db.Column(db.DateTime, default=datetime.utcnow)
    user_name = db.Column(db.String(255), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'contacted', 'resolved'
    contacted_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'question': self.question,
            'times_asked': self.times_asked,
            'first_asked': self.first_asked.isoformat(),
            'last_asked': self.last_asked.isoformat(),
            'user_name': self.user_name,
            'user_email': self.user_email,
            'status': self.status,
            'contacted_at': self.contacted_at.isoformat() if self.contacted_at else None
        }
    
    def __repr__(self):
        return f'<UnansweredQuestion {self.question[:50]}>'

class LeadCapture(db.Model):
    """Lead capture model - stores user info when confidence is low"""
    __tablename__ = 'lead_captures'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    user_name = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    question_context = db.Column(db.Text, nullable=True)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_name': self.user_name,
            'user_email': self.user_email,
            'question_context': self.question_context,
            'captured_at': self.captured_at.isoformat()
        }
    
    def __repr__(self):
        return f'<LeadCapture {self.user_email}>'

class BrandingSettings(db.Model):
    """Branding configuration model - stores widget customization"""
    __tablename__ = 'branding_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    bot_name = db.Column(db.String(255), default='ChatBot')
    bot_description = db.Column(db.String(500), default="We're here to help")
    primary_color = db.Column(db.String(7), default='#667eea')  # Hex color
    secondary_color = db.Column(db.String(7), default='#764ba2')
    accent_color = db.Column(db.String(7), default='#4CAF50')
    logo_url = db.Column(db.String(500), nullable=True)
    favicon_url = db.Column(db.String(500), nullable=True)
    custom_css = db.Column(db.Text, nullable=True)
    initial_message = db.Column(db.Text, default="Hi! 👋 How can I help you today?")
    position = db.Column(db.String(20), default='bottom-right')  # bottom-right, bottom-left, top-right, top-left
    theme_mode = db.Column(db.String(10), default='light')  # light or dark
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'bot_name': self.bot_name,
            'bot_description': self.bot_description,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color': self.accent_color,
            'logo_url': self.logo_url,
            'favicon_url': self.favicon_url,
            'custom_css': self.custom_css,
            'initial_message': self.initial_message,
            'position': self.position,
            'theme_mode': self.theme_mode,
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<BrandingSettings {self.bot_name}>'

# Import new models from package siblings so package exposes unified API
from .site import Site  # noqa: F401
from .intent import Intent, IntentPhrase, Workflow, ClientConfig  # noqa: F401
from .chat_log import ChatLog  # noqa: F401