from database import db
from datetime import datetime


class Site(db.Model):
    """Site / tenant model for multi-tenant SaaS"""
    __tablename__ = 'sites'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), nullable=True, unique=True)
    domain_whitelist = db.Column(db.Text, nullable=True)  # Comma-separated domains allowed
    theme = db.Column(db.String(50), nullable=True)
    bot_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships (backrefs kept minimal to avoid circular imports)
    intents = db.relationship('Intent', backref='site', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'domain_whitelist': self.domain_whitelist,
            'theme': self.theme,
            'bot_name': self.bot_name,
            'created_at': self.created_at.isoformat()
        }
    
    def is_domain_allowed(self, request_domain: str) -> bool:
        """Check if request_domain is whitelisted for this site"""
        if not self.domain_whitelist:
            return True
        allowed = [d.strip() for d in self.domain_whitelist.split(',')]
        return request_domain in allowed

    def __repr__(self):
        return f'<Site {self.name} ({self.id})>'
