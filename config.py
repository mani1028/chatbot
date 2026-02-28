"""
Configuration file for AI Chatbot application
"""
import os
from datetime import timedelta
from dotenv import load_dotenv # Run: pip install python-dotenv

load_dotenv()

# Flask app configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'default-unsecure-key-change-me')
DEBUG = os.getenv('DEBUG', 'True') == 'True'




# Prefer env DATABASE_URL, else use relative sqlite path (cross-platform)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

DB_PATH = os.path.join(INSTANCE_DIR, 'chatbot.db')

SQLALCHEMY_DATABASE_URI = "sqlite:///chatbot.db"
SQLALCHEMY_TRACK_MODIFICATIONS = False
# AI Service configuration
# CHANGED: Lowered to 0.65 to be more friendly in the simulator
CONFIDENCE_THRESHOLD = 0.65 

# Session configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# Admin credentials
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# Default fallback messages loaded from file
FALLBACK_MESSAGES = []
fallback_path = os.path.join(BASE_DIR, 'fallback_messages.txt')
if os.path.exists(fallback_path):
    with open(fallback_path, encoding='utf-8') as f:
        FALLBACK_MESSAGES = [line.strip() for line in f if line.strip()]
else:
    FALLBACK_MESSAGES = [
        "I'm not sure how to answer that. Could you rephrase your question?",
        "I don't have enough information to answer that. Please contact our support team.",
        "That's a great question! Let me connect you with a team member who can help.",
    ]

# CRM WebHook Configuration
CRM_WEBHOOK_URL = os.getenv('CRM_WEBHOOK_URL', 'http://localhost:5001/api/webhook/handoff')
CRM_WEBHOOK_KEY = os.getenv('CRM_WEBHOOK_KEY', 'your-webhook-key-here')

HANDOFF_KEYWORDS = [
    'agent', 'human', 'representative', 'help', 'support',
    'manager', 'live chat', 'speak to', 'call me'
]

SESSION_HISTORY_MAX = 10 
WIDGET_EMBED_URL = os.getenv('WIDGET_EMBED_URL', 'http://localhost:5000')

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
    'position': 'bottom-right',
    'theme_mode': 'light' 
}

WIDGET_WIDTH = 420
WIDGET_HEIGHT = 600
WIDGET_MIN_WIDTH = 300
WIDGET_MIN_HEIGHT = 400