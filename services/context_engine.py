"""
Smart Context Engine

Detects patterns in conversation:
- Confusion detection (repeated same answers)
- Escalation triggers (user anger, repeated failures)
- Intent patterns (what user actually wants vs what they said)
- Abnormal behavior (too many turns, timeouts)

This moves chatbot from "rule-based" to "intelligent."
"""

from models.conversation_thread import ConversationThread
from services.memory_compression import MemoryRecaller
from typing import Dict, List, Optional, Any
from config import FRUSTRATION_ESCALATION_THRESHOLD, ensure_thread_integrity
import logging
import re

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """
    Analyze conversation context for patterns and intelligence.
    
    Detects:
    - Confusion (user repeating, asking same thing)
    - Frustration (sentiment shift, angry keywords)
    - Intent drift (user changing mind mid-workflow)
    - Abnormal patterns (too fast, too slow, too many retries)
    """
    
    # Markers
    ANGER_KEYWORDS = [
        'angry', 'frustrated', 'upset', 'annoyed', 'furious',
        'why', 'ridiculous', 'stupid', 'awful', 'terrible',
        'never', "don't work", "doesn't work", 'broken'
    ]
    
    CONFUSION_KEYWORDS = [
        'confused', 'unclear', 'what', 'huh', 'pardon', 'again',
        'repeat', 'say that', 'same thing', 'didn\'t understand'
    ]
    
    ESCALATION_KEYWORDS = [
        'human', 'manager', 'support', 'help', 'speak to',
        'agent', 'representative', 'person', 'real person'
    ]
    
    IMPATIENCE_KEYWORDS = [
        'hurry', 'fast', 'quick', 'slow', 'waiting', 'come on',
        'now', 'asap', 'urgent', 'immediate'
    ]
    
    @staticmethod
    def detect_frustration(thread: ConversationThread) -> float:
        """
        Detect frustration level (0-1.0).
        
        Based on:
        - Anger keywords frequency
        - Escalation requests
        - Repeated failures
        - Time pressure
        """
        try:
            score = 0.0
            
            # Recent messages suggest current mood
            recent = MemoryRecaller.recall_recent_messages(thread, count=3) or []
            
            for msg in (recent or []):
                if msg['role'] == 'user':
                    text = msg['content'].lower()
                    
                    # Anger keywords (0.3 each)
                    anger_count = sum(1 for kw in ContextAnalyzer.ANGER_KEYWORDS if kw in text)
                    score += min(0.3, anger_count * 0.1)
                    
                    # Escalation requests (0.2 each)
                    escalation_count = sum(1 for kw in ContextAnalyzer.ESCALATION_KEYWORDS if kw in text)
                    score += min(0.2, escalation_count * 0.15)
                    
                    # Impatience (0.1)
                    if any(kw in text for kw in ContextAnalyzer.IMPATIENCE_KEYWORDS):
                        score += 0.1
                    
                    # Unknown intents increasing (0.2)
                    if (thread.unknown_intent_count or 0) > 2:
                        score += 0.2
            
            # Cap at 1.0
            return min(1.0, score)
        except Exception:
            # Default to safe value if anything fails
            return 0.0
    
    @staticmethod
    def detect_confusion(thread: ConversationThread) -> float:
        """
        Detect user confusion (0-1.0).
        
        Based on:
        - Repeated answers
        - Questions about what was asked
        - Multiple attempts on same step
        """
        try:
            score = 0.0
            
            # Check for confusion keywords in recent messages
            recent = MemoryRecaller.recall_recent_messages(thread, count=5) or []
            
            confusion_mentions = 0
            for msg in (recent or []):
                if msg['role'] == 'user':
                    text = msg['content'].lower()
                    if any(kw in text for kw in ContextAnalyzer.CONFUSION_KEYWORDS):
                        confusion_mentions += 1
                        score += 0.2
            
            # Heuristic: If user has repeated actions, likely confused
            # (Approximated by: still on same step after 3+ turns)
            if (thread.total_turns or 0) > 6 and (thread.steps_completed or 0) < 3:
                score += 0.3
            
            # Cap at 1.0
            return min(1.0, score)
        except Exception:
            # Default to safe value if anything fails
            return 0.0
    
    @staticmethod
    def detect_intent_drift(thread: ConversationThread) -> Optional[str]:
        """Detect if user is asking about something different from current workflow"""
        try:
            intent_shift_keywords = {
                'billing': ['price', 'cost', 'billing', 'invoice', 'payment'],
                'technical': ['error', 'bug', 'crash', 'broke'],
                'account': ['password', 'login', 'account', 'user']
            }
            recent = MemoryRecaller.recall_recent_messages(thread, count=5) or []
            
            for msg in (recent or []):
                if msg['role'] == 'user':
                    text = msg['content'].lower()
                    
                    for intent, keywords in intent_shift_keywords.items():
                        if any(kw in text for kw in keywords):
                            # Check if this is different from workflow intent
                            if thread.workflow_type and intent not in thread.workflow_type.lower():
                                return intent
            
            return None
        except Exception:
            # Default to safe value if anything fails
            return None
    
    @staticmethod
    def should_escalate_to_human(thread: ConversationThread) -> tuple[bool, Optional[str]]:
        """
        Intelligent decision: Should we escalate to human?
        
        Returns: (should_escalate, reason)
        
        Reasons:
        - 'high_frustration'
        - 'repeated_failures'
        - 'request_human'
        - 'intent_mismatch'
        - 'workflow_dropout'
        """
        try:
            # Rule 1: User explicitly asked for help
            recent = MemoryRecaller.recall_recent_messages(thread, count=1) or []
            if recent and len(recent) > 0:
                last_msg = recent[-1]
                if last_msg and isinstance(last_msg, dict):
                    text = last_msg.get('content', '').lower()
                    if any(kw in text for kw in ContextAnalyzer.ESCALATION_KEYWORDS):
                        return True, 'user_requested_human'
            
            # Rule 2: High frustration detected
            frustration = ContextAnalyzer.detect_frustration(thread) or 0.0
            if frustration > FRUSTRATION_ESCALATION_THRESHOLD:
                return True, 'high_frustration'
            
            # Rule 3: Too many unknown intents (3+)
            if (thread.unknown_intent_count or 0) >= 3:
                return True, 'repeated_unknown_intents'
            
            # Rule 4: Too many turns on same step (stuck)
            if (thread.total_turns or 0) > 10 and (thread.steps_completed or 0) < 3:
                return True, 'workflow_stuck'
            
            # Rule 5: Intent drift detected
            new_intent = ContextAnalyzer.detect_intent_drift(thread)
            if new_intent:
                return True, f'intent_drift_to_{new_intent}'
            
            return False, None
        except Exception:
            # Default to safe value - don't escalate on error
            return False, None
    
    @staticmethod
    def analyze_full_context(thread: ConversationThread) -> Dict[str, Any]:
        """
        Full context analysis (debugging/dashboard).
        
        Returns:
        {
            'frustration': 0.6,
            'confusion': 0.2,
            'should_escalate': (True, 'high_frustration'),
            'intent_drift': None,
            'patterns': {...}
        }
        """
        
        return {
            'frustration_level': round(ContextAnalyzer.detect_frustration(thread), 2),
            'confusion_level': round(ContextAnalyzer.detect_confusion(thread), 2),
            'should_escalate': ContextAnalyzer.should_escalate_to_human(thread),
            'intent_drift': ContextAnalyzer.detect_intent_drift(thread),
            'state': {
                'workflow': thread.workflow_type,
                'current_step': thread.current_step,
                'steps_completed': thread.steps_completed,
                'total_turns': thread.total_turns,
                'unknown_intents': thread.unknown_intent_count
            }
        }


class PatternDetector:
    """
    Detect behavioral patterns across conversations.
    
    Answers questions like:
    - What step causes most drop-off?
    - Which intents fail most?
    - What time of day has issues?
    """
    
    @staticmethod
    def find_bottleneck_steps(site_id: str, workflow_type: str) -> List[Dict[str, Any]]:
        """
        Identify workflow steps with high abandonment.
        
        Returns: [{step, abandonment_rate, recommendation}]
        """
        
        from models.conversation_thread import ConversationThread
        from datetime import timedelta
        from datetime import datetime
        
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        threads = ConversationThread.query.filter(
            ConversationThread.site_id == site_id,
            ConversationThread.workflow_type == workflow_type,
            ConversationThread.created_at >= cutoff
        ).all()
        
        # GATE 4: Ensure thread integrity
        for thread in threads:
            ensure_thread_integrity(thread)
        
        if not threads:
            return []
        
        # Map step abandonment
        step_data = {}
        for thread in threads:
            step = thread.current_step
            if step:
                if step not in step_data:
                    step_data[step] = {'total': 0, 'completed': 0}
                
                step_data[step]['total'] += 1
                if thread.workflow_status == 'completed':
                    step_data[step]['completed'] += 1
        
        # Calculate and sort by abandonment
        bottlenecks = []
        for step, data in step_data.items():
            if data['total'] > 0:
                abandon_rate = 1.0 - (data['completed'] / data['total'])
                
                bottlenecks.append({
                    'step': step,
                    'abandonment_rate': round(abandon_rate, 2),
                    'total_users': data['total'],
                    'completed': data['completed'],
                    'recommendation': PatternDetector._get_recommendation(step, abandon_rate)
                })
        
        # Sort by abandonment rate
        return sorted(bottlenecks, key=lambda x: x['abandonment_rate'], reverse=True)
    
    @staticmethod
    def _get_recommendation(step: str, abandon_rate: float) -> str:
        """Get recommendation for high-abandonment step"""
        
        if abandon_rate > 0.5:
            return f"Critical: {step.replace('_', ' ')} has very high drop-off"
        elif abandon_rate > 0.3:
            return f"Simplify or clarify: {step.replace('_', ' ')}"
        else:
            return f"Monitor: {step.replace('_', ' ')} performs normally"
