"""
Webhook Configuration - Per-site configurable webhooks for events.
Replaces the hardcoded CRM_WEBHOOK_URL with a flexible per-tenant system.
"""
from database import db
from datetime import datetime
import json


class WebhookConfig(db.Model):
    """Per-site webhook configuration for various events."""
    __tablename__ = 'webhook_configs'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)

    name = db.Column(db.String(255), nullable=False)            # e.g. 'Slack Notification'
    
    # Event types: handoff, form_complete, lead_capture, escalation, new_conversation
    event_type = db.Column(db.String(50), nullable=False)

    url = db.Column(db.String(500), nullable=False)
    method = db.Column(db.String(10), default='POST')           # POST, PUT
    
    # Custom headers as JSON: {"Authorization": "Bearer xxx", "X-Custom": "value"}
    headers_json = db.Column(db.Text, default='{}')
    
    # Optional payload template (JSON with {placeholders})
    payload_template = db.Column(db.Text, nullable=True)

    # Retry configuration
    max_retries = db.Column(db.Integer, default=3)
    timeout_seconds = db.Column(db.Integer, default=10)

    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_triggered = db.Column(db.DateTime, nullable=True)
    last_status_code = db.Column(db.Integer, nullable=True)

    def get_headers(self):
        try:
            return json.loads(self.headers_json or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_headers(self, headers: dict):
        self.headers_json = json.dumps(headers)

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'name': self.name,
            'event_type': self.event_type,
            'url': self.url,
            'method': self.method,
            'headers': self.get_headers(),
            'payload_template': self.payload_template,
            'max_retries': self.max_retries,
            'timeout_seconds': self.timeout_seconds,
            'enabled': self.enabled,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'last_status_code': self.last_status_code,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class WebhookLog(db.Model):
    """Logs webhook delivery attempts for debugging."""
    __tablename__ = 'webhook_logs'

    id = db.Column(db.Integer, primary_key=True)
    webhook_id = db.Column(db.Integer, db.ForeignKey('webhook_configs.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)

    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.Text, nullable=True)
    
    status_code = db.Column(db.Integer, nullable=True)
    response_body = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text, nullable=True)

    attempt = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    webhook = db.relationship('WebhookConfig', backref='logs')

    def to_dict(self):
        return {
            'id': self.id,
            'webhook_id': self.webhook_id,
            'site_id': self.site_id,
            'event_type': self.event_type,
            'status_code': self.status_code,
            'success': self.success,
            'error_message': self.error_message,
            'attempt': self.attempt,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
