"""
Intent models for the chatbot.
"""
from database import db
from datetime import datetime

class Intent(db.Model):
    """Intent definition for a given site (tenant)"""
    __tablename__ = 'intents'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    intent_name = db.Column(db.String(255), nullable=False)
    intent_type = db.Column(db.String(20), nullable=False, default='info')
    sector = db.Column(db.String(50), nullable=True)
    confidence = db.Column(db.Float, default=0.8)
    confidence_threshold = db.Column(db.Float, default=0.7)
    response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    phrases = db.relationship('IntentPhrase', backref='intent', lazy='dynamic', cascade='all, delete-orphan')
    # Workflows relationship is defined in Workflow model or can be backref here
    # We will let Workflow define the backref or define it here if needed.
    # workflows = db.relationship('Workflow', backref='intent', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'intent_name': self.intent_name,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'response': self.response,
            'phrases': [p.phrase for p in self.phrases]
            ,'config_required': self.config_required
        }

    def __repr__(self):
        return f'<Intent {self.intent_name} ({self.id})>'

    @property
    def config_required(self):
        # This dictionary MUST match the names in your intent_templates/*.json files
        mapping = {
            'CHECK_PRICE': ['consultation_price'],
            'VISITING_HOURS': ['open_time', 'close_time'],
            'BUSINESS_HOURS': ['open_time', 'close_time'],
            'CLIENT_INQUIRY': ['lead_name', 'lead_email', 'lead_phone'],
            # Add new industry-specific keys here as you add new intent_templates
        }
        return mapping.get(self.intent_name, [])

class IntentPhrase(db.Model):
    """Phrase examples used to detect intent"""
    __tablename__ = 'intent_phrases'

    id = db.Column(db.Integer, primary_key=True)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=False)
    phrase = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f'<IntentPhrase {self.phrase[:40]}>'


class Workflow(db.Model):
    """Workflows map an intent to a callable handler"""
    __tablename__ = 'workflows'

    id = db.Column(db.Integer, primary_key=True)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=False)
    function_name = db.Column(db.String(255), nullable=False)

    intent = db.relationship('Intent', backref=db.backref('workflows', lazy='dynamic'))

    def __repr__(self):
        return f'<Workflow {self.function_name} for intent {self.intent_id}>'