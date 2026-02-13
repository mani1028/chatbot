from database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(db.Model):
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

class ClientConfig(db.Model):
    __tablename__ = 'client_config'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=True)

class UnansweredQuestion(db.Model):
    __tablename__ = 'unanswered_questions'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    times_asked = db.Column(db.Integer, default=1)
    last_asked = db.Column(db.DateTime, default=datetime.utcnow)

class LeadCapture(db.Model):
    __tablename__ = 'lead_captures'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BrandingSettings(db.Model):
    __tablename__ = 'branding_settings'
    id = db.Column(db.Integer, primary_key=True)
    bot_name = db.Column(db.String(100), default="AI Assistant")
    bot_description = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(20), default="#007bff")
    secondary_color = db.Column(db.String(20), default="#6c757d")
    accent_color = db.Column(db.String(20), default="#4CAF50")
    logo_url = db.Column(db.String(255), nullable=True)
    favicon_url = db.Column(db.String(255), nullable=True)
    custom_css = db.Column(db.Text, nullable=True)
    initial_message = db.Column(db.String(255), nullable=True)
    position = db.Column(db.String(20), default="bottom-right")
    theme_mode = db.Column(db.String(20), default="light")
    
    def to_dict(self):
        return {
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
            'theme_mode': self.theme_mode
        }

# Imports at the bottom to register with SQLAlchemy
from .site import Site
from .intent import Intent, IntentPhrase, Workflow
from .chat_log import ChatLog
from .plan import Plan, Subscription
from .platform_settings import PlatformSetting
from .sector_template import SectorTemplate