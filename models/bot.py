from database import db
from datetime import datetime

class Bot(db.Model):
    __tablename__ = 'bots'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Add more fields as needed (e.g., config, type, etc.)

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'name': self.name,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
