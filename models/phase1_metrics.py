"""
Phase 1 Analytics - Append-Only Metrics Log

This is NOT transactional state. It's a write-optimized analytics log.
No updates. No deletes. Indexes on: timestamp, tenant_id, phase_version.
"""
from database import db
from datetime import datetime

class Phase1Metrics(db.Model):
    """
    Per-request metrics capture for Phase 1 analytics.
    Append-only design for reliability and query optimization.
    """
    __tablename__ = 'phase1_metrics'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Tenant/Site context
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    site_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    message_id = db.Column(db.String(50), nullable=False, index=True)  # Indexed but NOT unique (append-only telemetry)
    
    # Timestamp (critical for analytics queries)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Intent Detection Results
    intent_name = db.Column(db.String(100), nullable=True)
    intent_confidence = db.Column(db.Float, nullable=True)
    confidence_band = db.Column(db.String(20), nullable=True)  # HIGH|MID|LOW
    
    # Clarification Logic
    clarification_triggered = db.Column(db.Boolean, default=False, nullable=False)
    clarification_message = db.Column(db.String(255), nullable=True)
    clarification_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    clarification_denied = db.Column(db.Boolean, default=False, nullable=False)
    
    # LLM Decision
    llm_called = db.Column(db.Boolean, default=False, nullable=False)
    llm_response_time_ms = db.Column(db.Integer, nullable=True)
    
    # Workflow Context
    workflow_active = db.Column(db.Boolean, default=False, nullable=False)
    workflow_type = db.Column(db.String(50), nullable=True)
    
    # Performance Metrics
    total_response_time_ms = db.Column(db.Integer, nullable=True)
    
    # System Version (for A/B testing and rollback tracking)
    phase_version = db.Column(db.String(10), default='1.0.0', nullable=False, index=True)
    
    # Execution summary (for debugging)
    execution_trace_summary = db.Column(db.String(500), nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return (f"<Phase1Metrics {self.message_id}: "
                f"intent={self.intent_name}, "
                f"clarification={self.clarification_triggered}, "
                f"llm={self.llm_called}>")
    
    @staticmethod
    def create_from_orchestrator(site_id, tenant_id, session_id, message_id, 
                                 orchestrator_result, thread, start_time, phase_version='1.0.0'):
        """
        Factory method to create metrics entry from orchestrator result.
        Call this AFTER orchestrator completes, BEFORE HTTP response.
        """
        import time
        end_time = time.time()
        total_ms = int((end_time - start_time) * 1000)
        
        # Determine confidence band
        confidence = orchestrator_result.get('intent_confidence', 0.0)
        if confidence >= 0.8:
            band = 'HIGH'
        elif confidence >= 0.55:
            band = 'MID'
        else:
            band = 'LOW'
        
        # Extract execution summary (last 3 trace items)
        trace_summary = None
        if thread and hasattr(thread, 'execution_trace'):
            trace_items = thread.execution_trace[-3:] if thread.execution_trace else []
            trace_summary = ' → '.join(str(t) for t in trace_items)
        
        metrics = Phase1Metrics(
            tenant_id=tenant_id,
            site_id=site_id,
            session_id=session_id,
            message_id=message_id,
            
            # Intent
            intent_name=orchestrator_result.get('intent_name'),
            intent_confidence=confidence,
            confidence_band=band,
            
            # Clarification
            clarification_triggered=thread.pending_clarification is not None if thread else False,
            clarification_message=thread.pending_reply if thread and hasattr(thread, 'pending_reply') else None,
            clarification_confirmed='clarification_confirmed' in str(thread.execution_trace) if thread and hasattr(thread, 'execution_trace') else False,
            clarification_denied='clarification_denied' in str(thread.execution_trace) if thread and hasattr(thread, 'execution_trace') else False,
            
            # LLM
            llm_called=orchestrator_result.get('used_llm', False),
            
            # Workflow
            workflow_active=bool(thread.workflow_type) if thread else False,
            workflow_type=thread.workflow_type if thread else None,
            
            # Performance
            total_response_time_ms=total_ms,
            
            # Version tracking
            phase_version=phase_version,
            
            # Debug
            execution_trace_summary=trace_summary
        )
        
        return metrics
