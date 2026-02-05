"""
Configuration file for AI Chatbot application
"""
import os
from datetime import timedelta

# Flask app configuration
SECRET_KEY = 'your-secret-key-change-in-production'
DEBUG = True

# Database configuration
SQLALCHEMY_DATABASE_URI = 'sqlite:///chatbot.db'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# AI Service configuration - Confidence thresholds
CONFIDENCE_THRESHOLD = 0.7  # Overall fallback threshold
HIGH_CONFIDENCE_THRESHOLD = 0.8  # Use detailed response
MEDIUM_CONFIDENCE_THRESHOLD = 0.5  # Use short response + follow-up
LOW_CONFIDENCE_THRESHOLD = 0.5  # Trigger handoff

# Session configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# Get absolute path to database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'chatbot.db')

# Admin credentials (for initial login)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Intent categories
INTENT_CATEGORIES = [
    'Software Development',
    'AI/ML',
    'Pricing',
    'Support',
    'General'
]

# Handoff settings
HANDOFF_REQUIRED_CATEGORIES = ['Pricing', 'Support']

# Default fallback messages
FALLBACK_MESSAGES = [
    "I'm not sure how to answer that. Could you rephrase your question?",
    "I don't have enough information to answer that. Would you like to speak with an expert?",
    "That's a great question! Let me connect you with a team member who can help.",
]

# Lead capture form settings
LEAD_CAPTURE_MESSAGE = "Thank you for your interest! To provide you with the best assistance, could you please share your contact information?"

# Confidence engine responses
CONFIDENCE_RESPONSES = {
    'high': "Based on our knowledge base, here's the detailed answer:",
    'medium': "Here's what I found that might help:",
    'low': "I'm not entirely sure about this. Would you like to speak with a specialist?"
}

# Email/contact settings (optional, for lead assignment)
SUPPORT_EMAIL = 'support@example.com'
SUPPORT_PHONE = '1-800-EXAMPLE'
