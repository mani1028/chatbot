"""
Configuration file for AI Chatbot application
"""
import os
from datetime import timedelta

# Flask app configuration
SECRET_KEY = 'your-secret-key-change-in-production'
DEBUG = True

# Get absolute path to database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'chatbot.db')

# Database configuration - use absolute path for reliability
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH.replace(chr(92), "/")}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# AI Service configuration
CONFIDENCE_THRESHOLD = 0.7  # Only answer if confidence >= 0.7

# Session configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# Admin credentials (for initial login)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Default fallback messages
FALLBACK_MESSAGES = [
    "I'm not sure how to answer that. Could you rephrase your question?",
    "I don't have enough information to answer that. Please contact our support team.",
    "That's a great question! Let me connect you with a team member who can help.",
]

# CRM WebHook Configuration
CRM_WEBHOOK_URL = os.getenv('CRM_WEBHOOK_URL', 'http://localhost:5001/api/webhook/handoff')
CRM_WEBHOOK_KEY = os.getenv('CRM_WEBHOOK_KEY', 'your-webhook-key-here')

# Handoff Keywords - trigger CRM webhook if user mentions these
HANDOFF_KEYWORDS = [
    'agent', 'human', 'representative', 'help', 'support',
    'manager', 'supervisor', 'live chat', 'speak to',
    'call me', 'contact me', 'help me', 'urgent',
    'problem', 'issue', 'complaint', 'frustrated'
]

# Session configuration for conversation history
SESSION_HISTORY_MAX = 10  # Store last 10 messages per session

# ===== WIDGET & BRANDING CONFIGURATION =====

# Widget embedding configuration
WIDGET_EMBED_URL = os.getenv('WIDGET_EMBED_URL', 'http://localhost:5000')
WIDGET_ENABLE_CORS = os.getenv('WIDGET_ENABLE_CORS', 'true').lower() == 'true'

# Default Branding Settings
DEFAULT_BRANDING = {
    'bot_name': 'AlinaX ChatBot',
    'bot_description': "We're here to help",
    'primary_color': '#667eea',
    'secondary_color': '#764ba2',
    'accent_color': '#4CAF50',
    'logo_url': None,
    'favicon_url': None,
    'custom_css': '',
    'initial_message': "Hi I'am AlinaX! 👋 How can I help you today?",
    'position': 'bottom-right',  # bottom-right, bottom-left, top-right, top-left
    'theme_mode': 'light'  # light or dark
}

# Widget sizing
WIDGET_WIDTH = 420  # pixels
WIDGET_HEIGHT = 600  # pixels
WIDGET_MIN_WIDTH = 300
WIDGET_MIN_HEIGHT = 400

