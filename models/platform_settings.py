
from database import db
from datetime import datetime

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, nullable=False)
    site_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PlatformSetting(db.Model):
    """
    Key-Value store for global SaaS configurations.
    Examples: 'OPENAI_API_KEY', 'STRIPE_WEBHOOK_SECRET', 'MASTER_ADMIN_EMAIL'
    """
    __tablename__ = 'platform_settings_kv'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value, # Be careful returning secrets!
            'description': self.description,
            'updated_at': self.updated_at.isoformat()
        }