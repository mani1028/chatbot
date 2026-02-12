from database import db
from datetime import datetime


class Intent(db.Model):
    """Intent definition for a given site (tenant)"""
    __tablename__ = 'intents'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    intent_name = db.Column(db.String(255), nullable=False)
    # intent_type: 'action' or 'info' (or 'LEAD'/'HUMAN' for handoff semantics)
    intent_type = db.Column(db.String(20), nullable=False, default='info')
    # sector for reuse across industries (e.g., hospital, travel, ecommerce)
    sector = db.Column(db.String(50), nullable=True)
    # configurable confidence threshold for this intent
    confidence = db.Column(db.Float, default=0.8)
    confidence_threshold = db.Column(db.Float, default=0.7)
    response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    phrases = db.relationship('IntentPhrase', backref='intent', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'intent_name': self.intent_name,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'response': self.response,
            'phrases': [p.phrase for p in self.phrases]
        }

    def __repr__(self):
        return f'<Intent {self.intent_name} ({self.id})>'


class IntentPhrase(db.Model):
    """Phrase examples used to detect intent"""
    __tablename__ = 'intent_phrases'

    id = db.Column(db.Integer, primary_key=True)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=False)
    phrase = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f'<IntentPhrase {self.phrase[:40]}>'


class Workflow(db.Model):
    """Workflows map an intent to a callable handler (function_name)"""
    __tablename__ = 'workflows'

    id = db.Column(db.Integer, primary_key=True)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=False)
    function_name = db.Column(db.String(255), nullable=False)

    intent = db.relationship('Intent', backref=db.backref('workflows', lazy='dynamic'))

    def __repr__(self):
        return f'<Workflow {self.function_name} for intent {self.intent_id}>'


class ClientConfig(db.Model):
    """Simple key/value config per client/site"""
    __tablename__ = 'client_config'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<ClientConfig {self.client_id}:{self.key}>'
