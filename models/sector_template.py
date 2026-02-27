from database import db
from datetime import datetime

class SectorTemplate(db.Model):
    """
    Blueprints for different industries (e.g. 'Hospital', 'E-commerce').
    Stores the JSON structure defining intents, phrases, and workflows.
    """
    __tablename__ = 'sector_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    
    # Stores the JSON structure (intents, phrases, config_required)
    # SQLite has no native JSON type, so we use Text.
    # In PostgreSQL, use JSONB.
    structure_json = db.Column(db.Text, nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            # structure_json is heavy, so we might not include it in list views
            'created_at': self.created_at.isoformat()
        }