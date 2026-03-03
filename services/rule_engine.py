"""
Rule Engine Layer

Executes decision rules BEFORE LLM call.

This:
- Reduces LLM dependency
- Handles special cases efficiently
- Implements business logic
- Fast + deterministic

Example rules:
- If urgent: escalate, don't answer
- If user angry: apologize, offer escalation
- If on step N: require entity E
- If pattern X detected: route to handler
"""

from models.conversation_thread import ConversationThread
from services.context_engine import ContextAnalyzer
from typing import Dict, Optional, List, Any, Callable
import logging

logger = logging.getLogger(__name__)


class Rule:
    """Base rule class"""
    
    def __init__(self, name: str, priority: int = 100):
        self.name = name
        self.priority = priority  # Higher = executes first
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        """Check if rule applies"""
        raise NotImplementedError
    
    def execute(self, thread: ConversationThread, user_message: str) -> Optional[Dict[str, Any]]:
        """Execute rule action"""
        raise NotImplementedError


class EscalationRule(Rule):
    """Escalate to human if frustration high"""
    
    def __init__(self):
        super().__init__("Escalation on Frustration", priority=1000)
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        should_escalate, reason = ContextAnalyzer.should_escalate_to_human(thread)
        self.escalation_reason = reason
        return should_escalate
    
    def execute(self, thread: ConversationThread, user_message: str) -> Dict[str, Any]:
        thread.escalate_workflow()
        return {
            'action': 'escalate',
            'bot_reply': 'I understand, let me connect you with a human agent. One moment please...',
            'reason': self.escalation_reason,
            'route_to_human': True
        }


class ConfusionRule(Rule):
    """Offer clarification if user confused"""
    
    def __init__(self):
        super().__init__("Offer Clarification", priority=800)
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        confusion = ContextAnalyzer.detect_confusion(thread)
        return confusion > 0.5
    
    def execute(self, thread: ConversationThread, user_message: str) -> Dict[str, Any]:
        return {
            'action': 'clarify',
            'bot_reply': 'I sense some confusion. Let me simplify: We\'re currently at the step where we need your {current_entity}. Could you try answering that?',
            'continue_workflow': True
        }


class IntentMismatchRule(Rule):
    """User asking about something different"""
    
    def __init__(self):
        super().__init__("Intent Mismatch Detection", priority=900)
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        drift = ContextAnalyzer.detect_intent_drift(thread)
        self.new_intent = drift
        return drift is not None
    
    def execute(self, thread: ConversationThread, user_message: str) -> Dict[str, Any]:
        return {
            'action': 'address_mismatch',
            'bot_reply': f'I see you\'re asking about {self.new_intent}. After we finish here, I can help with that. For now, shall we continue with {thread.workflow_type}?',
            'continue_workflow': True,
            'defer_intent': self.new_intent
        }


class SpeedLimitRule(Rule):
    """If user answering too fast/slow, check for bots or issues"""
    
    def __init__(self):
        super().__init__("Speed Anomaly Detection", priority=600)
        self.min_time_between_messages = 2  # seconds
        self.max_time_between_messages = 3600  # 1 hour
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        from datetime import datetime
        
        if not thread.short_term_messages or len(thread.short_term_messages) < 2:
            return False
        
        last_msg = thread.short_term_messages[-2]
        if not last_msg or not isinstance(last_msg, dict):
            return False
            
        last_time = last_msg.get('timestamp')
        if not last_time:
            return False
        
        try:
            last_dt = datetime.fromisoformat(last_time)
            time_diff = (datetime.utcnow() - last_dt).total_seconds()
            
            # Anomaly: too fast (bot-like) or too slow (user abandoned)
            return time_diff < self.min_time_between_messages or \
                   time_diff > self.max_time_between_messages
        except:
            return False
    
    def execute(self, thread: ConversationThread, user_message: str) -> Dict[str, Any]:
        from datetime import datetime
        
        last_msg = thread.short_term_messages[-2]
        if not last_msg or not isinstance(last_msg, dict):
            return {'action': 'none'}
            
        last_time = last_msg.get('timestamp')
        if not last_time:
            return {'action': 'none'}
            
        try:
            last_dt = datetime.fromisoformat(last_time)
            time_diff = (datetime.utcnow() - last_dt).total_seconds()
        except:
            return {'action': 'none'}
        
        if time_diff < self.min_time_between_messages:
            # Too fast - likely automated
            return {
                'action': 'speed_check',
                'bot_reply': 'That was very quick! Just confirming you\'re human. Please continue.',
                'continue_workflow': True
            }
        else:
            # Too slow - likely abandoned then returned
            thread.extend_ttl(minutes=30)  # Reset timeout
            return {
                'action': 'session_resume',
                'bot_reply': f'Welcome back! We were at: {thread.current_step}. Ready to continue?',
                'continue_workflow': True
            }


class UnknownIntentRule(Rule):
    """Handle repeated unknown intents"""
    
    def __init__(self):
        super().__init__("Unknown Intent Threshold", priority=700)
        self.max_unknowns = 3
    
    def matches(self, thread: ConversationThread, user_message: str) -> bool:
        return thread.unknown_intent_count >= self.max_unknowns
    
    def execute(self, thread: ConversationThread, user_message: str) -> Dict[str, Any]:
        return {
            'action': 'escalate_unknown',
            'bot_reply': 'I\'m having trouble understanding. Would you like to describe your need differently, or should I connect you with someone?',
            'offer_escalation': True,
            'continue_workflow': False
        }


class RuleEngine:
    """
    Execute rules before LLM.
    
    Rules are evaluated by priority.
    First matching rule wins (by default).
    """
    
    def __init__(self):
        self.rules: List[Rule] = [
            EscalationRule(),
            IntentMismatchRule(),
            UnknownIntentRule(),
            ConfusionRule(),
            SpeedLimitRule()
        ]
        # Sort by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def evaluate(
        self,
        thread: ConversationThread,
        user_message: str
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate all rules, return action if any match.
        
        Returns: {action, bot_reply, ...} or None if no rules match
        """
        
        for rule in self.rules:
            try:
                if rule.matches(thread, user_message):
                    logger.info(f"Rule matched: {rule.name}")
                    result = rule.execute(thread, user_message)
                    result['matched_rule'] = rule.name
                    return result
            except Exception as e:
                logger.error(f"Rule error: {rule.name} - {e}")
                continue
        
        return None
    
    def add_rule(self, rule: Rule):
        """Add custom rule"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str):
        """Remove rule by name"""
        self.rules = [r for r in self.rules if r.name != rule_name]


# Global instance
_rule_engine = None

def get_rule_engine() -> RuleEngine:
    """Get or create global rule engine"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
