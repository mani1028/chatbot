"""
ConversationThread Model - Master data structure for all conversations.

This replaces the old per-message ChatLog approach.
Now we track entire conversation sessions with:
- Workflow state
- Memory (short-term, structured, summary)
- Scoring metrics
- Thread status
- Multi-tenant isolation
"""

from database import db
from datetime import datetime, timedelta
import json

class ConversationThread(db.Model):
    """
    Master thread for a conversation session.
    
    One thread = one complete user interaction workflow
    Examples:
    - "User came in, booked appointment, thread closed"
    - "User had question, got escalated to human"
    - "User abandoned at step 3"
    """
    
    __tablename__ = 'conversation_thread'
    
    # ============ IDENTIFIERS ============
    id = db.Column(db.String(50), primary_key=True)  # UUID
    site_id = db.Column(db.String(100), index=True, nullable=False)
    session_id = db.Column(db.String(100), index=True, nullable=False)
    user_id = db.Column(db.String(100), nullable=True)  # Optional: logged-in user
    
    # ============ WORKFLOW INFO ============
    workflow_type = db.Column(db.String(50), nullable=True)  # "booking", "lead_capture", "support"
    workflow_status = db.Column(
        db.String(20),
        default='active',
        nullable=False
    )  # active, completed, escalated, abandoned
    current_step = db.Column(db.String(50), nullable=True)  # "collecting_email"
    steps_completed = db.Column(db.Integer, default=0)
    
    # ============ MEMORY DATA ============
    # Short-term: Last 5 messages (quick lookup)
    short_term_messages = db.Column(db.JSON, default=list)  # [{role, content, timestamp}]
    
    # Structured: Extracted entities
    structured_data = db.Column(db.JSON, default=dict)  # {name, email, phone, date, time}
    
    # Long-term: Compressed summary (for LLM context)
    long_term_summary = db.Column(db.Text, nullable=True)
    # Example: "User booking haircut for tomorrow at 2pm, email john@test.com"
    
    # ============ SCORING & METRICS ============
    completion_score = db.Column(db.Float, default=0.0)  # 0-1.0
    escalation_triggered = db.Column(db.Boolean, default=False)
    escalation_reason = db.Column(db.String(100), nullable=True)  # Why escalated
    unknown_intent_count = db.Column(db.Integer, default=0)  # Repeated escalation trigger
    last_intent_confidence = db.Column(db.Float, default=0.0)
    avg_response_time = db.Column(db.Float, nullable=True)  # milliseconds
    total_turns = db.Column(db.Integer, default=0)  # bot + user messages combined
    
    # ============ CONTEXT ANALYSIS (Phase 2) ============
    frustration_score = db.Column(db.Float, default=0.0)  # 0-1.0
    confusion_score = db.Column(db.Float, default=0.0)  # 0-1.0
    intent_drift = db.Column(db.String(100), nullable=True)  # New intent detected
    recommendation = db.Column(db.String(50), default='continue')  # Action recommendation
    context_engine_enabled = db.Column(db.Boolean, default=True)
    rule_engine_enabled = db.Column(db.Boolean, default=True)
    
    # ============ EXECUTION TRACE ============
    execution_trace = db.Column(db.JSON, default=list)  # Ordered list of executed stages
    
    # ============ TIMESTAMPS ============
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # 30 min TTL
    
    # ============ METADATA ============
    client_ip = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    language = db.Column(db.String(10), default='en')
    
    # ============ REPLY STATE (Phase 2) ============
    # ONLY reply state during message processing
    # Cleared after finalize() appends to history
    # Never persisted long-term; only for transient processing
    pending_reply = db.Column(db.Text, nullable=True)  # Current reply being built
    last_detected_intent = db.Column(db.String(100), nullable=True)  # For analytics
    used_llm = db.Column(db.Boolean, default=False)  # Did this turn use LLM?
    llm_confidence = db.Column(db.Float, nullable=True)
    
    # ============ PHASE 1: CLARIFICATION BAND ============
    # Tracks pending clarification questions (e.g., "Did you mean X?")
    # Persists across requests so user can confirm/deny intent
    pending_clarification = db.Column(db.String(255), nullable=True, index=True)
    
    # ============ RELATIONSHIPS ============
    # Note: ChatLog is now a separate model in models/chat_log.py
    # The relationship has been removed to avoid SQLAlchemy conflicts
    
    def __init__(self, site_id, session_id, **kwargs):
        self.id = self._generate_id()
        self.site_id = site_id
        self.session_id = session_id
        self.expires_at = datetime.utcnow() + timedelta(minutes=30)
        # Initialize mutable fields to prevent None errors
        if 'short_term_messages' not in kwargs:
            self.short_term_messages = []
        if 'structured_data' not in kwargs:
            self.structured_data = {}
        if 'execution_trace' not in kwargs:
            self.execution_trace = []
        super().__init__(**kwargs)
    
    @staticmethod
    def _generate_id():
        """Generate unique thread ID"""
        import uuid
        return f"thread_{uuid.uuid4().hex[:12]}"
    
    def has_active_workflow(self) -> bool:
        """Semantic check: Does this thread have an active workflow?
        
        GATE 3 ENFORCEMENT: Provides semantic interface for workflow blocking.
        Used by orchestrator to determine if LLM should be called.
        """
        return bool(self.workflow_type and self.workflow_status == 'active')
    
    # ============ MEMORY OPERATIONS ============
    # NOTE: Message appending ONLY happens in MessageOrchestrator
    # DO NOT append messages here or in any service
    # This ensures deterministic state mutation
    
    def update_structured_data(self, entities):
        """Update extracted entities"""
        if isinstance(entities, dict):
            self.structured_data.update(entities)
    
    def generate_summary(self):
        """
        Compress short-term + structured into LLM-friendly summary.
        
        Example output:
        "User booking service: haircut. Name: John Smith. Email: john@test.com.
         Preferred date: tomorrow. Status: collecting time."
        """
        parts = []
        
        if self.workflow_type:
            parts.append(f"Workflow: {self.workflow_type}")
        
        if self.structured_data:
            parts.append("Collected info: " + ", ".join(
                [f"{k}: {v}" for k, v in self.structured_data.items()]
            ))
        
        if self.workflow_status == 'escalated':
            parts.append("Status: Escalated to human support")
        
        self.long_term_summary = ". ".join(parts)
        return self.long_term_summary
    
    def get_context_for_llm(self):
        """
        Return lightweight context for LLM (optimized for tokens).
        
        Returns:
        {
            'short_term': last 5 messages,
            'structured': {name, email, ...},
            'summary': "User booking haircut..."
        }
        """
        return {
            'short_term': self.short_term_messages[-3:] if self.short_term_messages else [],
            'structured': self.structured_data,
            'summary': self.long_term_summary or self.generate_summary()
        }
    
    # ============ SCORING OPERATIONS ============
    
    def calculate_completion_score(self):
        """
        Calculate workflow completion (0-1.0).
        
        Factors:
        - Steps completed / total steps in workflow
        - No unknown intents
        - Quick response times
        """
        if not self.workflow_type:
            return 0.0
        
        # Define total steps per workflow
        workflow_steps = {
            'booking': 9,
            'lead_capture': 7,
            'support': 6
        }
        
        total = workflow_steps.get(self.workflow_type, 5)
        base_score = self.steps_completed / total
        
        # Penalty for unknown intents
        unknown_penalty = min(0.3, self.unknown_intent_count * 0.1)
        
        # Penalty for low confidence
        confidence_penalty = max(0, 1.0 - self.last_intent_confidence) * 0.2
        
        self.completion_score = max(0.0, base_score - unknown_penalty - confidence_penalty)
        return self.completion_score
    
    def should_escalate(self):
        """
        Intelligence: Should we escalate to human?
        
        Triggers:
        - 3+ unknown intents in a row
        - User explicitly asks
        - Workflow marked as escalated
        """
        if self.unknown_intent_count >= 3:
            return True
        
        if self.workflow_status == 'escalated':
            return True
        
        return False
    
    # ============ WORKFLOW OPERATIONS ============
    
    def advance_workflow(self, next_step):
        """Transition to next workflow step"""
        self.current_step = next_step
        self.steps_completed += 1
        self.last_message_at = datetime.utcnow()
    
    def complete_workflow(self):
        """Mark workflow as completed"""
        self.workflow_status = 'completed'
        self.completed_at = datetime.utcnow()
        self.calculate_completion_score()
    
    def escalate_workflow(self):
        """Mark workflow as escalated to human"""
        self.workflow_status = 'escalated'
        self.escalation_triggered = True
    
    def abandon_workflow(self):
        """Mark workflow as abandoned"""
        self.workflow_status = 'abandoned'
        self.last_message_at = datetime.utcnow()
    
    # ============ UTILITY ============
    
    def is_expired(self):
        """Check if thread has expired (30 min TTL)"""
        return datetime.utcnow() > self.expires_at
    
    def extend_ttl(self, minutes=30):
        """Extend expiration time"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
    
    def to_dict(self):
        """Serialize to JSON"""
        return {
            'id': self.id,
            'site_id': self.site_id,
            'session_id': self.session_id,
            'workflow_type': self.workflow_type,
            'workflow_status': self.workflow_status,
            'current_step': self.current_step,
            'steps_completed': self.steps_completed,
            'completion_score': round(self.completion_score, 2),
            'structured_data': self.structured_data,
            'unknown_intent_count': self.unknown_intent_count,
            'escalation_triggered': self.escalation_triggered,
            'created_at': self.created_at.isoformat(),
            'last_message_at': self.last_message_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

