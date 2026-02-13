from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance
db = SQLAlchemy()

def init_db(app):
    """
    Initializes the database tables.
    Called from app.py within the application context.
    """
    # Import models here to ensure they are known to SQLAlchemy before creation
    # This prevents circular imports since models import 'db' from this file
    import models
    
    with app.app_context():
        db.create_all()