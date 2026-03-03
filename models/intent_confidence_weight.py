"""
Tracks intent success metrics for confidence weighting.
"""
from database import db
from datetime import datetime


class IntentConfidenceWeight(db.Model):
    """
    Tracks success rate per intent to adjust confidence multipliers.
    
    Logic:
    - If intent X has 90% successful resolutions → boost weight
    - If intent Y has 30% escalation → reduce weight
    - Effective confidence = base_confidence × success_weight
    
    This self-tunes the system based on real outcomes.
    """
    __tablename__ = 'intent_confidence_weights'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    intent_id = db.Column(db.Integer, db.ForeignKey('intents.id'), nullable=False)
    
    # Metrics
    total_detections = db.Column(db.Integer, default=0)
    successful_resolutions = db.Column(db.Integer, default=0)
    escalations = db.Column(db.Integer, default=0)
    user_corrections = db.Column(db.Integer, default=0)  # User said "no" to clarification
    
    # Calculated
    success_rate = db.Column(db.Float, default=0.8)  # 0.0-1.0
    escalation_rate = db.Column(db.Float, default=0.0)
    
    # Applied weight (0.4-1.2)
    # 0.4 = intent is risky, reduce confidence
    # 1.0 = neutral
    # 1.2 = intent is reliable, boost confidence
    confidence_multiplier = db.Column(db.Float, default=1.0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def recalculate_weight(self) -> None:
        """
        Recalculate confidence multiplier based on metrics.
        
        Formula:
            success_weight = success_rate
            escalation_penalty = escalation_rate × 0.5
            correction_penalty = (user_corrections / total) × 0.3
            
            multiplier = max(0.4, min(1.2, 1.0 - escalation_penalty - correction_penalty))
        """
        if self.total_detections == 0:
            self.confidence_multiplier = 1.0
            return
        
        # Success rate (higher is better)
        self.success_rate = self.successful_resolutions / self.total_detections
        
        # Escalation rate
        self.escalation_rate = self.escalations / self.total_detections
        
        # Penalties
        escalation_penalty = self.escalation_rate * 0.5
        correction_rate = self.user_corrections / self.total_detections
        correction_penalty = correction_rate * 0.3
        
        # Compute multiplier
        base = 1.0
        multiplier = base - escalation_penalty - correction_penalty
        
        # Clamp to [0.4, 1.2]
        self.confidence_multiplier = max(0.4, min(1.2, multiplier))
        self.last_updated = datetime.utcnow()

    def record_detection(self) -> None:
        """Record that this intent was detected."""
        self.total_detections += 1
        self.recalculate_weight()

    def record_success(self) -> None:
        """Record that intent detection led to successful resolution."""
        self.successful_resolutions += 1
        self.recalculate_weight()

    def record_escalation(self) -> None:
        """Record that intent detection led to escalation."""
        self.escalations += 1
        self.recalculate_weight()

    def record_user_correction(self) -> None:
        """Record that user corrected the intent (said 'no' to clarification)."""
        self.user_corrections += 1
        self.recalculate_weight()

    @classmethod
    def get_or_create(cls, site_id: int, intent_id: int):
        """Get or create weight tracker for intent."""
        w = cls.query.filter_by(site_id=site_id, intent_id=intent_id).first()
        if not w:
            w = cls(site_id=site_id, intent_id=intent_id)
            db.session.add(w)
            db.session.commit()
        return w

    def to_dict(self):
        return {
            'id': self.id,
            'intent_id': self.intent_id,
            'total_detections': self.total_detections,
            'success_rate': round(self.success_rate, 3),
            'escalation_rate': round(self.escalation_rate, 3),
            'confidence_multiplier': round(self.confidence_multiplier, 3),
            'last_updated': self.last_updated.isoformat()
        }

    def __repr__(self):
        return f'<IntentConfidenceWeight intent_id={self.intent_id} multiplier={self.confidence_multiplier:.2f}>'
