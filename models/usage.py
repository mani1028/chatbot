from database import db
from datetime import datetime

class Usage(db.Model):
    __tablename__ = 'usage'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    messages = db.Column(db.Integer, default=0)
    storage_mb = db.Column(db.Float, default=0)
    api_calls = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    month = db.Column(db.String(7), nullable=False)  # e.g. '2026-02'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'messages': self.messages,
            'storage_mb': self.storage_mb,
            'api_calls': self.api_calls,
            'active_users': self.active_users,
            'month': self.month,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
