"""
Conversation State Engine - Lightweight session context memory.
Tracks where a user is in a multi-turn flow (form filling, follow-ups, etc.)
"""
from database import db
from datetime import datetime, timedelta
import json


class ConversationState(db.Model):
    """Stores per-session conversation state for multi-turn flows."""
    __tablename__ = 'conversation_states'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    session_id = db.Column(db.String(255), nullable=False, index=True)

    # Current flow tracking
    active_intent = db.Column(db.String(255), nullable=True)   # e.g. 'order_tracking'
    current_step = db.Column(db.String(100), nullable=True)     # e.g. 'ask_order_id'
    flow_type = db.Column(db.String(50), nullable=True)         # 'form', 'followup', 'action'

    # Collected data during the flow (JSON blob)
    collected_data = db.Column(db.Text, default='{}')

    # Context memory - last N intents + metadata (JSON blob)
    context = db.Column(db.Text, default='{}')

    # Form tracking (if active_intent is a form)
    form_id = db.Column(db.Integer, db.ForeignKey('form_definitions.id'), nullable=True)
    form_step_index = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self):
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        # Auto-expire after 30 minutes of inactivity
        if self.updated_at and (datetime.utcnow() - self.updated_at) > timedelta(minutes=30):
            return True
        return False

    def get_collected_data(self):
        try:
            return json.loads(self.collected_data or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_collected_data(self, data: dict):
        self.collected_data = json.dumps(data)

    def add_collected_field(self, key: str, value):
        data = self.get_collected_data()
        data[key] = value
        self.set_collected_data(data)

    def get_context(self):
        try:
            return json.loads(self.context or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_context(self, ctx: dict):
        self.context = json.dumps(ctx)

    def update_context(self, **kwargs):
        """Merge new keys into existing context."""
        ctx = self.get_context()
        ctx.update(kwargs)
        # Keep last 5 intent history
        history = ctx.get('intent_history', [])
        if len(history) > 5:
            ctx['intent_history'] = history[-5:]
        self.set_context(ctx)

    def clear_flow(self):
        """Reset the active flow but keep context memory."""
        self.active_intent = None
        self.current_step = None
        self.flow_type = None
        self.form_id = None
        self.form_step_index = 0
        self.collected_data = '{}'

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'session_id': self.session_id,
            'active_intent': self.active_intent,
            'current_step': self.current_step,
            'flow_type': self.flow_type,
            'collected_data': self.get_collected_data(),
            'context': self.get_context(),
            'form_id': self.form_id,
            'form_step_index': self.form_step_index,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_expired': self.is_expired()
        }

    @staticmethod
    def get_or_create(site_id: int, session_id: str):
        """Get existing state or create a new one for the session."""
        state = ConversationState.query.filter_by(
            site_id=site_id, session_id=session_id
        ).first()
        if state and state.is_expired():
            # Expired - reset flow but keep the record
            state.clear_flow()
            state.set_context({})
            state.updated_at = datetime.utcnow()
            db.session.commit()
        if not state:
            state = ConversationState(
                site_id=site_id,
                session_id=session_id,
                collected_data='{}',
                context='{}'
            )
            db.session.add(state)
            db.session.commit()
        return state
