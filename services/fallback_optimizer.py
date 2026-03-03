"""
FallbackOptimizer: Core service for fallback rate reduction.

Handles:
1. Intent boosting with clarifying questions
2. Confidence throttling (prevent storms)
3. Success-based confidence weighting
4. Admin mapping orchestration
"""
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from database import db
from models import (
    Intent, IntentPhrase, UnknownIntentLog, ConfidenceThrottle,
    IntentConfidenceWeight
)
from config import classify_confidence


class FallbackOptimizer:
    """
    Reduces fallback rate through intelligent layering:
    - Intent boosting
    - Throttling
    - Confidence weighting
    - Auto-training
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ============================================================================
    # LAYER 1: INTENT BOOSTING (Clarifying Questions)
    # ============================================================================

    def generate_clarifying_questions(
        self,
        intent: Intent,
        message: str,
        site_id: int
    ) -> Optional[str]:
        """
        For medium-confidence matches, suggest specific sub-options instead of
        generic "Is this correct?"
        
        Example:
            Intent: billing_inquiry
            Message: "fees"
            Response: "Are you asking about:
                       1. Fee structure?
                       2. Current balance?
                       3. Payment options?"
        
        Args:
            intent: The matched intent
            message: User's message
            site_id: Tenant ID
        
        Returns:
            Clarifying question or None if using default flow
        """
        # Intent-specific question templates
        questions_map = {
            'billing_inquiry': self._clarify_billing,
            'refund_request': self._clarify_refund,
            'product_inquiry': self._clarify_product,
            'booking_request': self._clarify_booking,
            'support_request': self._clarify_support,
        }
        
        handler = questions_map.get(intent.intent_name)
        if handler:
            return handler(message, site_id)
        
        # Default: use generic clarification
        return None

    def _clarify_billing(self, message: str, site_id: int) -> str:
        """Billing-specific clarification."""
        keywords = message.lower()
        
        if any(word in keywords for word in ['fee', 'cost', 'price']):
            return "Are you asking about:\n1. Fee structure?\n2. Upcoming charges?\n3. Invoice details?"
        elif any(word in keywords for word in ['pay', 'payment', 'owed']):
            return "Do you want to:\n1. Make a payment?\n2. Check balance?\n3. View payment history?"
        elif any(word in keywords for word in ['discount', 'promo', 'coupon']):
            return "Are you looking for:\n1. Current promotions?\n2. Loyalty discounts?\n3. Bulk pricing?"
        
        return None

    def _clarify_refund(self, message: str, site_id: int) -> str:
        """Refund-specific clarification."""
        return "For your refund request:\n1. Check refund status?\n2. Initiate new refund?\n3. Escalate to support?"

    def _clarify_product(self, message: str, site_id: int) -> str:
        """Product inquiry clarification."""
        return "Are you asking about:\n1. Product details?\n2. Availability?\n3. Pricing?"

    def _clarify_booking(self, message: str, site_id: int) -> str:
        """Booking-specific clarification."""
        return "Do you want to:\n1. Make a new booking?\n2. Modify existing booking?\n3. Check availability?"

    def _clarify_support(self, message: str, site_id: int) -> str:
        """Support-specific clarification."""
        return "How can I help?\n1. Technical issue?\n2. Account problem?\n3. General question?"

    # ============================================================================
    # LAYER 2: THROTTLING (Prevent LLM Storms)
    # ============================================================================

    def should_throttle_fallback(
        self,
        site_id: int,
        session_id: str,
        confidence: float,
        throttle_seconds: int = 20
    ) -> Tuple[bool, str]:
        """
        Check if fallback should be throttled.
        
        Logic:
        - If fallback occurred in last 20 seconds
        - And this message is also low confidence
        - Return safe template instead of LLM
        
        Args:
            site_id: Tenant ID
            session_id: Conversation session ID
            confidence: Current message confidence
            throttle_seconds: Window to check (default 20s)
        
        Returns:
            (should_throttle: bool, reason: str)
        """
        # Only throttle if confidence is already low (save LLM for true unknowns)
        if confidence >= 0.55:
            return False, ""
        
        # Check throttle status
        if ConfidenceThrottle.should_throttle(site_id, session_id, throttle_seconds):
            return True, "Session throttled: multiple fallbacks in short time"
        
        return False, ""

    def record_fallback_event(
        self,
        site_id: int,
        session_id: str,
        message: str,
        fallback_type: str = 'llm',
        llm_response: Optional[str] = None
    ) -> UnknownIntentLog:
        """
        Log a fallback event for tracking and admin mapping.
        
        Args:
            site_id: Tenant ID
            session_id: Conversation session
            message: User message that triggered fallback
            fallback_type: 'llm', 'throttle', 'confidence'
            llm_response: LLM-generated response (if applicable)
        
        Returns:
            UnknownIntentLog record
        """
        log = UnknownIntentLog(
            site_id=site_id,
            message=message,
            llm_response=llm_response,
            fallback_type=fallback_type
        )
        db.session.add(log)
        
        # Also record throttle event
        ConfidenceThrottle.record_fallback(site_id, session_id)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to log fallback event: {e}")
        
        return log

    # ============================================================================
    # LAYER 3: CONFIDENCE WEIGHTING (Self-Tuning)
    # ============================================================================

    def get_effective_confidence(
        self,
        intent: Intent,
        base_confidence: float,
        site_id: int
    ) -> float:
        """
        Apply success-based multiplier to confidence score.
        
        Formula:
            effective_confidence = base_confidence × confidence_multiplier
        
        Multiplier is adjusted based on:
        - Historical success rate
        - Escalation frequency
        - User corrections
        
        Args:
            intent: The matched intent
            base_confidence: Original confidence from detector
            site_id: Tenant ID
        
        Returns:
            Adjusted confidence (0.0-1.0)
        """
        weight = IntentConfidenceWeight.get_or_create(site_id, intent.id)
        effective = base_confidence * weight.confidence_multiplier
        return min(1.0, max(0.0, effective))

    def record_intent_success(
        self,
        intent_id: int,
        site_id: int
    ) -> None:
        """
        Record that an intent was successfully resolved.
        
        This boosts the intent's confidence multiplier over time.
        """
        weight = IntentConfidenceWeight.get_or_create(site_id, intent_id)
        weight.record_detection()
        weight.record_success()
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to record intent success: {e}")

    def record_intent_escalation(
        self,
        intent_id: int,
        site_id: int
    ) -> None:
        """
        Record that an intent led to escalation.
        
        This reduces the intent's confidence multiplier.
        """
        weight = IntentConfidenceWeight.get_or_create(site_id, intent_id)
        weight.record_detection()
        weight.record_escalation()
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to record intent escalation: {e}")

    def record_user_correction(
        self,
        intent_id: int,
        site_id: int
    ) -> None:
        """
        Record that user said 'no' to a clarification question.
        
        This indicates the intent detection was wrong.
        """
        weight = IntentConfidenceWeight.get_or_create(site_id, intent_id)
        weight.record_user_correction()
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to record user correction: {e}")

    # ============================================================================
    # LAYER 4: PHRASE AUTO-TRAINING (Admin Mapping)
    # ============================================================================

    def map_unknown_to_intent(
        self,
        unknown_log_id: int,
        intent_id: int,
        site_id: int,
        admin_id: int,
        auto_train_phrases: bool = True
    ) -> Tuple[bool, str]:
        """
        Admin maps an unknown message to an intent.
        Optionally auto-trains the phrase.
        
        Args:
            unknown_log_id: UnknownIntentLog.id
            intent_id: Intent to map to
            site_id: Tenant ID
            admin_id: Admin who performed mapping
            auto_train_phrases: Auto-add phrase to intent?
        
        Returns:
            (success: bool, message: str)
        """
        try:
            # Fetch log and intent
            log = UnknownIntentLog.query.get(unknown_log_id)
            intent = Intent.query.get(intent_id)
            
            if not log or not intent:
                return False, "Unknown log or intent not found"
            
            if log.site_id != site_id or intent.site_id != site_id:
                return False, "Site mismatch"
            
            # Update log
            log.mapped_to_intent_id = intent_id
            log.admin_mapped_at = datetime.utcnow()
            log.admin_mapped_by = admin_id
            
            phrase_added = False
            if auto_train_phrases:
                # Check if phrase already exists
                existing = IntentPhrase.query.filter_by(
                    intent_id=intent_id,
                    phrase=log.message
                ).first()
                
                if not existing:
                    # Add phrase
                    new_phrase = IntentPhrase(
                        intent_id=intent_id,
                        phrase=log.message
                    )
                    db.session.add(new_phrase)
                    log.phrase_auto_trained = True
                    phrase_added = True
            
            db.session.commit()
            
            msg = f"Mapped '{log.message[:40]}' to {intent.intent_name}"
            if phrase_added:
                msg += " + phrase trained"
            
            return True, msg
        
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error mapping unknown intent: {e}")
            return False, str(e)

    # ============================================================================
    # ADMIN ANALYTICS
    # ============================================================================

    def get_unmapped_unknowns(
        self,
        site_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get most common unmapped unknown messages for admin review.
        
        Ordered by frequency (most common first).
        """
        logs = db.session.query(
            UnknownIntentLog.message,
            db.func.count(UnknownIntentLog.id).label('count')
        ).filter(
            UnknownIntentLog.site_id == site_id,
            UnknownIntentLog.mapped_to_intent_id == None
        ).group_by(
            UnknownIntentLog.message
        ).order_by(
            db.func.count(UnknownIntentLog.id).desc()
        ).limit(limit).all()
        
        return [
            {
                'message': msg,
                'count': count,
                'sample_log_id': UnknownIntentLog.query.filter_by(
                    site_id=site_id,
                    message=msg
                ).first().id
            }
            for msg, count in logs
        ]

    def get_intent_metrics(
        self,
        site_id: int,
        intent_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get confidence weight metrics for all intents (or specific intent).
        
        Useful for admin dashboard.
        """
        query = IntentConfidenceWeight.query.filter_by(site_id=site_id)
        
        if intent_id:
            query = query.filter_by(intent_id=intent_id)
        
        metrics = query.all()
        return [m.to_dict() for m in metrics]

    def get_fallback_stats(self, site_id: int) -> Dict:
        """
        Get fallback statistics for a site.
        """
        total_logs = UnknownIntentLog.query.filter_by(site_id=site_id).count()
        mapped_logs = UnknownIntentLog.query.filter(
            UnknownIntentLog.site_id == site_id,
            UnknownIntentLog.mapped_to_intent_id != None
        ).count()
        
        by_type = db.session.query(
            UnknownIntentLog.fallback_type,
            db.func.count(UnknownIntentLog.id)
        ).filter_by(site_id=site_id).group_by(
            UnknownIntentLog.fallback_type
        ).all()
        
        return {
            'total_fallbacks': total_logs,
            'mapped_count': mapped_logs,
            'unmapped_count': total_logs - mapped_logs,
            'coverage': round(mapped_logs / total_logs, 3) if total_logs > 0 else 0,
            'by_type': {ftype: count for ftype, count in by_type}
        }


# Global instance
_optimizer = FallbackOptimizer()

def get_optimizer() -> FallbackOptimizer:
    return _optimizer
