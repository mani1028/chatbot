"""
Database setup and session management
"""
from flask_sqlalchemy import SQLAlchemy
import os
from config import DATABASE_PATH

# Initialize SQLAlchemy
db = SQLAlchemy()

def init_db(app):
    """
    Initialize database with Flask app
    Creates all tables if they don't exist
    """
    with app.app_context():
        db.create_all()
        print(f"Database initialized at: {DATABASE_PATH}")

def get_db_session():
    """
    Get current database session
    """
    return db.session
