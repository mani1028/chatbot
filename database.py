"""
Database setup and session management
"""
from flask_sqlalchemy import SQLAlchemy
import os
from config import DATABASE_PATH

# Initialize SQLAlchemy instance
db = SQLAlchemy()

def init_db(app):
    """
    Initialize database with Flask app
    Creates all tables if they don't exist
    """
    # Ensure instance folder exists to avoid errors when creating DB
    db_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            print(f"Created directory: {db_dir}")
        except OSError as e:
            print(f"Error creating directory {db_dir}: {e}")

    # REMOVED: db.init_app(app) 
    # This is already called in app.py. Calling it twice causes the RuntimeError.
    
    # Create tables
    with app.app_context():
        try:
            db.create_all()
            print(f"Database initialized at: {DATABASE_PATH}")
        except Exception as e:
            print(f"Error initializing database: {e}")

def get_db_session():
    """
    Get current database session
    """
    return db.session