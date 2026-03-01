"""
Multi-Step Form Engine - Define and execute multi-step data collection forms.
Forms are tied to intents and walk users through fields one at a time.
"""
from database import db
from datetime import datetime
import json


class FormDefinition(db.Model):
    """Defines a multi-step form that can be triggered by an intent."""
    __tablename__ = 'form_definitions'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=True)

    name = db.Column(db.String(255), nullable=False)          # e.g. 'Contact Form'
    description = db.Column(db.Text, nullable=True)
    
    # JSON array of form steps:
    # [
    #   {"field": "name", "type": "text", "prompt": "What's your name?", "required": true},
    #   {"field": "email", "type": "email", "prompt": "What's your email?", "required": true, "validation": "email"},
    #   {"field": "phone", "type": "phone", "prompt": "Phone number?", "required": false},
    #   {"field": "issue", "type": "textarea", "prompt": "Describe your issue:", "required": true}
    # ]
    steps_json = db.Column(db.Text, nullable=False, default='[]')

    # Message shown after form completion
    completion_message = db.Column(db.Text, default='Thank you! Your information has been submitted.')

    # Where to send completed form data
    webhook_url = db.Column(db.String(500), nullable=True)     # Optional webhook on completion
    save_as_lead = db.Column(db.Boolean, default=True)          # Save to LeadCapture table

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    intent = db.relationship('Intent', backref=db.backref('form', uselist=False))

    def get_steps(self):
        try:
            return json.loads(self.steps_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def set_steps(self, steps: list):
        self.steps_json = json.dumps(steps)

    def get_step(self, index: int):
        steps = self.get_steps()
        if 0 <= index < len(steps):
            return steps[index]
        return None

    def step_count(self):
        return len(self.get_steps())

    def validate_field(self, step: dict, value: str) -> tuple:
        """
        Validate a field value against step rules.
        Returns (is_valid: bool, error_message: str or None)
        """
        import re

        field_type = step.get('type', 'text')
        required = step.get('required', False)
        validation = step.get('validation', '')

        # Check required
        if required and not value.strip():
            return False, f"This field is required. {step.get('prompt', '')}"

        # Skip validation for empty optional fields
        if not value.strip():
            return True, None

        # Built-in validation types
        if validation == 'email' or field_type == 'email':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value.strip()):
                return False, "Please enter a valid email address."

        elif validation == 'phone' or field_type == 'phone':
            cleaned = re.sub(r'[\s\-\(\)\+]', '', value)
            if not cleaned.isdigit() or len(cleaned) < 7:
                return False, "Please enter a valid phone number."

        elif validation == 'number' or field_type == 'number':
            try:
                float(value)
            except ValueError:
                return False, "Please enter a valid number."

        elif validation and validation.startswith('regex:'):
            pattern = validation[6:]
            if not re.match(pattern, value):
                return False, step.get('validation_error', 'Invalid format. Please try again.')

        return True, None

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'intent_id': self.intent_id,
            'name': self.name,
            'description': self.description,
            'steps': self.get_steps(),
            'completion_message': self.completion_message,
            'webhook_url': self.webhook_url,
            'save_as_lead': self.save_as_lead,
            'is_active': self.is_active,
            'step_count': self.step_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FormSubmission(db.Model):
    """Stores completed form submissions."""
    __tablename__ = 'form_submissions'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey('form_definitions.id'), nullable=False)
    session_id = db.Column(db.String(255), nullable=True)

    # All collected data as JSON
    data_json = db.Column(db.Text, nullable=False, default='{}')

    status = db.Column(db.String(20), default='completed')  # completed, partial, webhook_sent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    form = db.relationship('FormDefinition', backref='submissions')

    def get_data(self):
        try:
            return json.loads(self.data_json or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_data(self, data: dict):
        self.data_json = json.dumps(data)

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'form_id': self.form_id,
            'form_name': self.form.name if self.form else None,
            'session_id': self.session_id,
            'data': self.get_data(),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
