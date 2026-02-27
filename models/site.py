import uuid
from database import db
from datetime import datetime

class Site(db.Model):
    """Site / tenant model for multi-tenant SaaS"""
    __tablename__ = 'sites'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), nullable=True, unique=True)
    domain_whitelist = db.Column(db.Text, nullable=True)
    theme = db.Column(db.String(50), nullable=True)
    bot_name = db.Column(db.String(255), nullable=True)
    # Public key for secure widget authentication
    public_key = db.Column(db.String(100), unique=True, nullable=False, default=lambda: f"pk_live_{uuid.uuid4().hex[:16]}")
    
    # Expanded Fields
    status = db.Column(db.String(20), default='active') # active, suspended, trial
    owner_email = db.Column(db.String(120), nullable=True)
    
    # Usage metrics
    message_count = db.Column(db.Integer, default=0)
    
    # Foreign Keys
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    intents = db.relationship('Intent', backref='site', lazy='dynamic')
    plan = db.relationship('Plan', backref='sites')

    @property
    def is_active(self):
        return (self.status or 'active') == 'active'

    def to_dict(self):
        plan_name = self.plan.name if self.plan else 'No Plan'
        plan_limit = self.plan.max_monthly_chats if self.plan else 0
        return {
            'id': self.id,
            'name': self.name,
            'public_key': self.public_key,
            'domain': self.domain,
            'status': self.status,
            'is_active': self.is_active,
            'plan_name': plan_name,
            'usage_percent': int((self.message_count / plan_limit * 100)) if plan_limit > 0 else 0
        }
    
    def is_domain_allowed(self, request_domain: str) -> bool:
        if not self.domain_whitelist:
            return True
        allowed = [d.strip() for d in self.domain_whitelist.split(',')]
        return request_domain in allowed

    def __repr__(self):
        return f'<Site {self.name} ({self.id})>'