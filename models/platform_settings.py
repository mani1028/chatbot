

from database import db
from datetime import datetime
from utils.mask_secrets import mask_secrets

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
        # Mask secrets for sensitive keys
        sensitive_keys = ['OPENAI_API_KEY', 'STRIPE_WEBHOOK_SECRET']
        val = self.value
        if self.key in sensitive_keys:
            val = mask_secrets(val)
        return {
            'key': self.key,
            'value': val,
            'description': self.description,
            'updated_at': self.updated_at.isoformat()
        }


# Utility to fetch OpenAI API key
def get_openai_api_key():
    import os
    from flask import has_app_context
    
    # Always try environment variable first (no DB context needed)
    env_key = os.getenv('OPENAI_API_KEY')
    if env_key and env_key != '' and env_key.startswith('sk-'):
        return env_key
    
    # If we have app context, check database
    if has_app_context():
        try:
            setting = PlatformSetting.query.filter_by(key='OPENAI_API_KEY').first()
            if setting and setting.value and setting.value.startswith('sk-'):
                return setting.value
        except Exception:
            pass
    
    # Fallback to env even if invalid format (let OpenAI handle the error)
    return env_key if env_key else None