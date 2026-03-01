from database import db
from datetime import datetime

class Plan(db.Model):
    """SaaS Billing Plans"""
    __tablename__ = 'plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True) # e.g. Starter, Pro
    price = db.Column(db.Float, default=0.0)
    
    # Limits
    max_intents = db.Column(db.Integer, default=50)
    max_monthly_chats = db.Column(db.Integer, default=1000) # Replaces/Aligns with message_limit
    max_forms = db.Column(db.Integer, default=3)             # Max form definitions per site
    max_webhooks = db.Column(db.Integer, default=2)          # Max webhook configs per site
    
    is_active = db.Column(db.Boolean, default=True)

    # Feature Gates - what's enabled per plan tier
    ai_enabled = db.Column(db.Boolean, default=False)        # LLM fallback + AI features
    workflows_enabled = db.Column(db.Boolean, default=True)  # ACTION intent workflows
    forms_enabled = db.Column(db.Boolean, default=True)      # Multi-step form engine
    analytics_enabled = db.Column(db.Boolean, default=False)  # Detailed analytics dashboard
    webhooks_enabled = db.Column(db.Boolean, default=False)   # Webhook-based handoffs
    custom_branding = db.Column(db.Boolean, default=False)    # Custom widget branding
    priority_support = db.Column(db.Boolean, default=False)   # Priority support flag
    
    # Backwards compatibility property if needed by legacy code
    @property
    def message_limit(self):
        return self.max_monthly_chats

    def get_features(self):
        """Return a dict of all feature gates for this plan."""
        return {
            'ai_enabled': self.ai_enabled,
            'workflows_enabled': self.workflows_enabled,
            'forms_enabled': self.forms_enabled,
            'analytics_enabled': self.analytics_enabled,
            'webhooks_enabled': self.webhooks_enabled,
            'custom_branding': self.custom_branding,
            'priority_support': self.priority_support,
            'max_intents': self.max_intents,
            'max_monthly_chats': self.max_monthly_chats,
            'max_forms': self.max_forms,
            'max_webhooks': self.max_webhooks,
        }

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'max_intents': self.max_intents,
            'max_monthly_chats': self.max_monthly_chats,
            'max_forms': self.max_forms,
            'max_webhooks': self.max_webhooks,
            'is_active': self.is_active,
            'ai_enabled': self.ai_enabled,
            'workflows_enabled': self.workflows_enabled,
            'forms_enabled': self.forms_enabled,
            'analytics_enabled': self.analytics_enabled,
            'webhooks_enabled': self.webhooks_enabled,
            'custom_branding': self.custom_branding,
            'priority_support': self.priority_support,
        }

class Subscription(db.Model):
    """Links a Site to a Plan"""
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    
    is_active = db.Column(db.Boolean, default=True)
    current_billing_cycle_start = db.Column(db.DateTime, default=datetime.utcnow)
    current_billing_cycle_end = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    site = db.relationship('Site', backref=db.backref('subscription', uselist=False))
    plan = db.relationship('Plan')

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'plan_name': self.plan.name if self.plan else 'Unknown',
            'is_active': self.is_active,
            'cycle_start': self.current_billing_cycle_start.isoformat() if self.current_billing_cycle_start else None,
            'cycle_end': self.current_billing_cycle_end.isoformat() if self.current_billing_cycle_end else None
        }