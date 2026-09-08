"""
Unknown intent logging with full audit trail.

Tracks messages that triggered UNKNOWN fallback, with complete mapping history.
Enables admin review, one-click mapping, auto-training, and ROI measurement.
"""
from database import db
from datetime import datetime
from sqlalchemy import Index


class UnknownIntentLog(db.Model):
    """
    Comprehensive unknown intent tracking.
    
    Fields:
    - message: The user's message that wasn't understood
    - fallback_type: Why fallback happened ('llm', 'throttle', 'confidence')
    - llm_response: The AI's fallback response (for debugging)
    - resolved: Has admin mapped this to an intent?
    - mapped_intent_id: Target intent ID (if admin mapped)
    - mapped_by: Admin ID who performed mapping
    - mapped_at: When mapping occurred
    - phrase_auto_trained: Was message auto-added as phrase?
    """
    __tablename__ = 'unknown_intent_logs'

    # Primary & tracking
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Message & context
    message = db.Column(db.Text, nullable=False)
    llm_response = db.Column(db.Text, nullable=True)  # The fallback response user saw
    fallback_type = db.Column(
        db.String(50),
        default='llm',
        nullable=False,
        comment="Why fallback occurred: 'llm', 'throttle', 'confidence'"
    )
    
    # Mapping & resolution (Phase 1 → admin action)
    resolved = db.Column(db.Boolean, default=False, index=True)
    mapped_intent_id = db.Column(db.Integer, nullable=True, index=True)  # Foreign key to Intent
    mapped_by = db.Column(db.Integer, nullable=True)  # Admin ID who mapped
    mapped_at = db.Column(db.DateTime, nullable=True)  # When admin mapped
    phrase_auto_trained = db.Column(db.Boolean, default=False)  # Was phrase added to intent?
    
    # Audit
    __table_args__ = (
        Index('idx_site_unresolved', 'site_id', 'resolved'),
        Index('idx_fallback_type', 'fallback_type'),
    )
    
    def to_dict(self, include_admin_fields=True):
        """Convert to dict for API responses."""
        data = {
            'id': self.id,
            'site_id': self.site_id,
            'message': self.message,
            'fallback_type': self.fallback_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved': self.resolved,
        }
        
        if include_admin_fields:
            data.update({
                'llm_response': self.llm_response,
                'mapped_intent_id': self.mapped_intent_id,
                'mapped_by': self.mapped_by,
                'mapped_at': self.mapped_at.isoformat() if self.mapped_at else None,
                'phrase_auto_trained': self.phrase_auto_trained,
            })
        
        return data
    
    def __repr__(self):
        status = "✓ mapped" if self.resolved else "✗ unmapped"
        return f'<UnknownIntentLog({self.id}) {status}: "{self.message[:40]}">'
