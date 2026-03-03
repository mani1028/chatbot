"""
Tracks fallback frequency per session to prevent storms.
"""
from database import db
from datetime import datetime, timedelta


class ConfidenceThrottle(db.Model):
    """
    Prevents fallback storms by tracking LLM call frequency per session.
    
    Logic:
    - If same session had fallback in last 20 seconds
    - And next message is also low confidence
    - → Don't call LLM, return safe template instead
    
    This prevents cascading failures.
    """
    __tablename__ = 'confidence_throttles'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    session_id = db.Column(db.String(255), nullable=False)  # From request session
    
    # Fallback tracking
    fallback_count = db.Column(db.Integer, default=0)
    last_fallback_at = db.Column(db.DateTime, nullable=True)
    
    # Reset window
    window_start = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def should_throttle(cls, site_id: int, session_id: str, throttle_seconds: int = 20) -> bool:
        """
        Check if a fallback in last N seconds occurred.
        
        Returns True if throttle should apply (don't call LLM).
        """
        if not session_id:
            return False
        
        throttle = cls.query.filter_by(site_id=site_id, session_id=session_id).first()
        if not throttle:
            return False
        
        time_since_last = datetime.utcnow() - throttle.last_fallback_at
        if time_since_last < timedelta(seconds=throttle_seconds):
            return True
        
        # Window expired, reset
        throttle.fallback_count = 0
        throttle.window_start = datetime.utcnow()
        db.session.commit()
        return False

    @classmethod
    def record_fallback(cls, site_id: int, session_id: str) -> None:
        """Record that a fallback occurred in this session."""
        if not session_id:
            return
        
        throttle = cls.query.filter_by(site_id=site_id, session_id=session_id).first()
        if not throttle:
            throttle = cls(site_id=site_id, session_id=session_id)
            db.session.add(throttle)
        
        throttle.fallback_count += 1
        throttle.last_fallback_at = datetime.utcnow()
        throttle.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()

    def __repr__(self):
        return f'<ConfidenceThrottle {self.session_id} (count={self.fallback_count})>'
