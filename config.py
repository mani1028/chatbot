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

# AI Service configuration
CONFIDENCE_THRESHOLD = 0.7  # Only answer if confidence >= 0.7

# Session configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# Get absolute path to database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'chatbot.db')

# Admin credentials (for initial login)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Default fallback messages
FALLBACK_MESSAGES = [
    "I'm not sure how to answer that. Could you rephrase your question?",
    "I don't have enough information to answer that. Please contact our support team.",
    "That's a great question! Let me connect you with a team member who can help.",
]
