"""
Conversation Scoring & Analytics

Measure:
- Completion rate (% workflows that finish)
- Drop-off rate (% that abandon at each step)
- Escalation rate (% that need human help)
- Average steps to completion
- Unknown intent frequency
- User satisfaction proxy

This turns the chatbot into a measurable system.
"""

from models.conversation_thread import ConversationThread
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from database import db
from config import ensure_thread_integrity
import logging

logger = logging.getLogger(__name__)


class ConversationScorer:
    """
    Calculate quality metrics for conversations.
    
    Scores individual threads on:
    - Efficiency (how many steps to complete)
    - Clarity (how many unknown intents)
    - Confidence (intent confidence levels)
    - Satisfaction (proxy: escalation, repetition)
    """
    
    # Weight factors for different metrics
    EFFICIENCY_WEIGHT = 0.25  # Fewer steps = higher score
    CLARITY_WEIGHT = 0.25     # Fewer unknowns = higher score
    CONFIDENCE_WEIGHT = 0.25  # Higher intent confidence = higher score
    SATISFACTION_WEIGHT = 0.25 # No escalation = higher score
    
    @staticmethod
    def score_thread(thread: ConversationThread) -> float:
        """
        Calculate overall quality score (0-1.0) for thread.
        
        Based on:
        - Steps to completion (efficiency)
        - Unknown intent count (clarity)
        - Intent confidence (precision)
        - Non-escalation (satisfaction)
        """
        
        # Base completion score (already calculated)
        base = thread.completion_score or 0.0
        
        # Efficiency: Penalty for extra steps
        # Ideal = minimum steps, each step collects required entity
        # Penalty: 0.05 per extra step beyond minimum
        extra_steps = max(0, thread.steps_completed - 5)  # 5 is typical
        efficiency = max(0.0, 1.0 - (extra_steps * 0.05))
        
        # Clarity: Penalty for unknown intents
        # Each unknown intent = 0.1 deduction
        clarity = max(0.0, 1.0 - (thread.unknown_intent_count * 0.1))
        
        # Confidence: Bonus for high intent confidence
        confidence = thread.last_intent_confidence or 0.5
        
        # Satisfaction: Penalty for escalation
        satisfaction = 0.5 if thread.escalation_triggered else 1.0
        
        # Weighted average
        overall_score = (
            base * ConversationScorer.EFFICIENCY_WEIGHT +
            efficiency * 0.15 +
            clarity * ConversationScorer.CLARITY_WEIGHT +
            confidence * ConversationScorer.CONFIDENCE_WEIGHT +
            satisfaction * ConversationScorer.SATISFACTION_WEIGHT
        )
        
        thread.completion_score = max(0.0, min(1.0, overall_score))
        return thread.completion_score
    
    @staticmethod
    def category_score(
        thread: ConversationThread,
        category: str
    ) -> float:
        """
        Score specific category.
        
        Categories: efficiency, clarity, confidence, satisfaction
        """
        
        if category == 'efficiency':
            # 1.0 if 5 steps, 0.9 if 6 steps, 0.8 if 7 steps, etc.
            return max(0.0, 1.0 - ((thread.steps_completed - 5) * 0.1))
        
        elif category == 'clarity':
            # Fewer unknowns = higher score
            return max(0.0, 1.0 - (thread.unknown_intent_count * 0.2))
        
        elif category == 'confidence':
            return thread.last_intent_confidence or 0.5
        
        elif category == 'satisfaction':
            return 0.5 if thread.escalation_triggered else 1.0
        
        return 0.0
    
    @staticmethod
    def drop_off_rate_per_step(site_id: str, workflow_type: str, days: int = 30) -> Dict[str, float]:
        """
        Calculate drop-off rate at each workflow step.
        
        Example output:
        {
            'collecting_name': 0.05,  # 5% abandon here
            'collecting_email': 0.08, # 8% abandon here
            'collecting_phone': 0.12  # 12% abandon here
        }
        """
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        threads = ConversationThread.query.filter(
            ConversationThread.site_id == site_id,
            ConversationThread.workflow_type == workflow_type,
            ConversationThread.created_at >= cutoff
        ).all()
        
        # GATE 4: Ensure thread integrity
        for thread in threads:
            ensure_thread_integrity(thread)
        
        if not threads:
            return {}
        
        # Count threads at each step
        step_counts = {}
        for thread in threads:
            if thread.current_step:
                step = thread.current_step
                if step not in step_counts:
                    step_counts[step] = {'total': 0, 'abandoned': 0}
                
                step_counts[step]['total'] += 1
                
                # Abandoned = not completed and inactive for 30+ min
                if thread.workflow_status == 'abandoned' or \
                   (thread.workflow_status == 'active' and \
                    (datetime.utcnow() - thread.last_message_at).total_seconds() > 1800):
                    step_counts[step]['abandoned'] += 1
        
        # Calculate drop-off rate
        drop_off = {}
        for step, counts in step_counts.items():
            if counts['total'] > 0:
                rate = counts['abandoned'] / counts['total']
                drop_off[step] = round(rate, 3)
        
        return drop_off


class ConversationAnalytics:
    """
    High-level analytics dashboard metrics.
    
    Aggregates conversation data into business metrics:
    - Completion rate
    - Escalation rate
    - Time to completion
    - User satisfaction proxy
    - Revenue impact (if applicable)
    """
    
    @staticmethod
    def get_site_metrics(site_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a site.
        
        Returns:
        {
            'total_conversations': 10,
            'completion_rate': 0.80,
            'escalation_rate': 0.10,
            'avg_steps': 5.2,
            'avg_time_to_complete': 180,
            'avg_score': 0.75,
            'by_workflow': {
                'booking': {...},
                'lead_capture': {...}
            }
        }
        """
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        threads = ConversationThread.query.filter(
            ConversationThread.site_id == site_id,
            ConversationThread.created_at >= cutoff
        ).all()
        
        # GATE 4: Ensure thread integrity
        for thread in threads:
            ensure_thread_integrity(thread)
        
        if not threads:
            return {
                'total_conversations': 0,
                'completion_rate': 0.0,
                'escalation_rate': 0.0,
                'avg_steps': 0,
                'avg_score': 0.0
            }
        
        completed = [t for t in threads if t.workflow_status == 'completed']
        escalated = [t for t in threads if t.escalation_triggered]
        
        # Time to completion (for completed workflows)
        completion_times = []
        for t in completed:
            if t.completed_at and t.created_at:
                duration = (t.completed_at - t.created_at).total_seconds() / 60
                completion_times.append(duration)
        
        metrics = {
            'total_conversations': len(threads),
            'completed': len(completed),
            'escalated': len(escalated),
            'abandoned': len([t for t in threads if t.workflow_status == 'abandoned']),
            'active': len([t for t in threads if t.workflow_status == 'active']),
            
            'completion_rate': len(completed) / len(threads) if threads else 0.0,
            'escalation_rate': len(escalated) / len(threads) if threads else 0.0,
            
            'avg_steps_to_complete': sum(t.steps_completed for t in completed) / len(completed) if completed else 0,
            'avg_score': sum(ConversationScorer.score_thread(t) for t in threads) / len(threads) if threads else 0.0,
            'avg_time_minutes': sum(completion_times) / len(completion_times) if completion_times else None,
            
            'unknown_intent_avg': sum((t.unknown_intent_count or 0) for t in threads) / len(threads) if threads else 0
        }
        
        # By workflow type
        by_workflow = {}
        workflow_types = set(t.workflow_type for t in threads if t.workflow_type)
        
        for wf_type in workflow_types:
            wf_threads = [t for t in threads if t.workflow_type == wf_type]
            wf_completed = [t for t in wf_threads if t.workflow_status == 'completed']
            
            by_workflow[wf_type] = {
                'total': len(wf_threads),
                'completed': len(wf_completed),
                'completion_rate': len(wf_completed) / len(wf_threads) if wf_threads else 0.0,
                'avg_score': sum(ConversationScorer.score_thread(t) for t in wf_threads) / len(wf_threads) if wf_threads else 0.0
            }
        
        metrics['by_workflow'] = by_workflow
        
        return metrics
    
    @staticmethod
    def get_quality_report(site_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Generate quality report (for dashboards/emails).
        
        Includes:
        - Overall quality score
        - Top issues
        - Recommendations
        """
        
        metrics = ConversationAnalytics.get_site_metrics(site_id, days)
        
        # Calculate overall quality (0-100 scale)
        quality_score = (
            metrics.get('completion_rate', 0) * 40 +  # Completion is 40%
            (1.0 - metrics.get('escalation_rate', 0)) * 30 +  # Low escalation is 30%
            metrics.get('avg_score', 0) * 30  # Average score is 30%
        ) * 100
        
        # Identify top issues
        issues = []
        
        if metrics.get('completion_rate', 0) < 0.70:
            issues.append({
                'severity': 'high',
                'issue': 'Low completion rate',
                'value': f"{metrics['completion_rate']*100:.1f}%",
                'threshold': '70%',
                'recommendation': 'Review workflow steps for clarity'
            })
        
        if metrics.get('escalation_rate', 0) > 0.20:
            issues.append({
                'severity': 'high',
                'issue': 'High escalation rate',
                'value': f"{metrics['escalation_rate']*100:.1f}%",
                'threshold': '20%',
                'recommendation': 'Improve intent recognition'
            })
        
        if metrics.get('unknown_intent_avg', 0) > 1.5:
            issues.append({
                'severity': 'medium',
                'issue': 'High unknown intents',
                'value': f"{metrics['unknown_intent_avg']:.2f} avg",
                'threshold': '1.5',
                'recommendation': 'Add more intent templates'
            })
        
        return {
            'quality_score': round(quality_score, 1),  # 0-100
            'quality_grade': ConversationAnalytics._score_to_grade(quality_score),
            'metrics': metrics,
            'issues': issues,
            'report_date': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _score_to_grade(score: float) -> str:
        """Convert 0-100 score to A-F grade"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
