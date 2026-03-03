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
# === GATE 2: CENTRALIZED THRESHOLD AUTHORITY ===
# All numerical thresholds defined here. No magic numbers scattered in code.

# Confidence classification thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.85       # Confident match - use intent response directly
MEDIUM_CONFIDENCE_THRESHOLD = 0.65     # Suggested match - ask for confirmation
LOW_CONFIDENCE_THRESHOLD = 0.0         # No match - escalate to LLM
ACTION_CONFIDENCE_THRESHOLD = 0.3      # Threshold for intent action eligibility
DEFAULT_INTENT_THRESHOLD = 0.65        # Default when importing/creating intents

# Emotional state thresholds
FRUSTRATION_ESCALATION_THRESHOLD = 0.7  # Frustration score that triggers escalation

CONFIDENCE_THRESHOLD = MEDIUM_CONFIDENCE_THRESHOLD  # For backwards compatibility

def classify_confidence(confidence_score: float) -> str:
    """
    Single authoritative function for confidence classification.
    
    GATE 2 ENFORCEMENT: All confidence decisions must go through this function.
    This ensures consistent threshold application across entire system.
    
    Args:
        confidence_score: Raw confidence value (0.0-1.0)
    
    Returns:
        "HIGH" - Use intent response directly (confidence >= 0.85)
        "MEDIUM" - Suggest intent, ask for confirmation (confidence >= 0.65)
        "LOW" - Unknown intent, escalate to LLM (confidence < 0.65)
    """
    if confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
        return "HIGH"
    elif confidence_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "MEDIUM"
    else:
        return "LOW"

def ensure_thread_integrity(thread):
    """
    GATE 4 ENFORCEMENT: Ensure all threads have valid state.
    
    Protects against NULL fields from old database rows.
    Call this immediately after loading a thread from database.
    
    Args:
        thread: ConversationThread instance
    
    Guarantees:
        - thread.short_term_messages is list (never None)
        - thread.structured_data is dict (never None)
        - thread.execution_trace is list (never None)
    """
    if not hasattr(thread, 'short_term_messages') or thread.short_term_messages is None:
        thread.short_term_messages = []
    
    if not hasattr(thread, 'structured_data') or thread.structured_data is None:
        thread.structured_data = {}
    
    if not hasattr(thread, 'execution_trace') or thread.execution_trace is None:
        thread.execution_trace = []
    
    return thread

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

# Check LLM Configuration
import logging
_llm_logger = logging.getLogger(__name__)
_openai_key = os.getenv('OPENAI_API_KEY', '').strip()
if not _openai_key:
    _llm_logger.warning("⚠️  LLM FALLBACK NOT CONFIGURED: OPENAI_API_KEY is missing")
    _llm_logger.warning("   Supports both OpenAI and OpenRouter API keys:")
    _llm_logger.warning("   ✓ OpenAI: sk-... (https://platform.openai.com/api-keys)")
    _llm_logger.warning("   ✓ OpenRouter: sk-or-... (https://openrouter.ai/keys)")
    _llm_logger.warning("   Update .env: OPENAI_API_KEY=your-key-here")
    _llm_logger.warning("   3. Restart the app")
elif not _openai_key.startswith(('sk-', 'sk-or-')):
    _llm_logger.warning("⚠️  LLM FALLBACK: API key format not recognized")
    _llm_logger.warning(f"   Key starts with: {_openai_key[:15]}...")
    _llm_logger.warning("   Expected: sk-... (OpenAI) or sk-or-... (OpenRouter)")
else:
    key_type = "OpenRouter" if _openai_key.startswith('sk-or-') else "OpenAI"
    _llm_logger.debug(f"✓ LLM Fallback configured successfully ({key_type})")