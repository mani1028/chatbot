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
    # FIX: Ensure the 'instance' directory exists before creating the DB
    db_dir = os.path.dirname(DATABASE_PATH)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir)
            print(f"Created directory: {db_dir}")
        except OSError as e:
            print(f"Error creating directory {db_dir}: {e}")

    with app.app_context():
        db.create_all()
        print(f"Database initialized at: {DATABASE_PATH}")

def get_db_session():
    """
    Get current database session
    """
    return db.session