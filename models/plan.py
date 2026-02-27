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
    
    is_active = db.Column(db.Boolean, default=True)
    
    # Backwards compatibility property if needed by legacy code
    @property
    def message_limit(self):
        return self.max_monthly_chats

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'max_intents': self.max_intents,
            'max_monthly_chats': self.max_monthly_chats,
            'is_active': self.is_active
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