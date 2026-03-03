"""
Generic Workflow Engine - Config-Driven FSM

This replaces the hardcoded BookingWorkflow, LeadCaptureWorkflow, etc.
Now all workflows are defined in JSON, engine is generic.

Benefits:
- No code changes for new workflows
- Admin-definable workflows
- Scalable to any workflow type
- Support for conditional logic, validation, etc.
"""

from services.workflow_config import get_workflow_config, WorkflowConfig
from services.entity_extractor import extract_entities
from models.conversation_thread import ConversationThread
from models.chat_log import ChatLog
from database import db
from config import ensure_thread_integrity
from datetime import datetime
from typing import Dict, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class GenericWorkflowEngine:
    """
    Universal workflow engine that works with ANY workflow config.
    
    No hardcoded logic - all driven by JSON configuration.
    """
    
    def __init__(self):
        self.config = get_workflow_config()
    
    # ============ WORKFLOW INITIALIZATION ============
    
    def start_workflow(
        self,
        workflow_type: str,
        site_id: str,
        session_id: str,
        user_id: Optional[str] = None,
        **metadata
    ) -> Optional[ConversationThread]:
        """
        Start a new workflow.
        
        Returns: ConversationThread or None if workflow not found
        """
        # Validate workflow exists
        workflow_config = self.config.get_workflow(workflow_type)
        if not workflow_config or not workflow_config.get('enabled'):
            logger.warning(f"Workflow {workflow_type} not found or disabled")
            return None
        
        # Create thread
        thread = ConversationThread(
            site_id=site_id,
            session_id=session_id,
            user_id=user_id,
            workflow_type=workflow_type,
            workflow_status='active'
        )
        
        # Set metadata
        if 'client_ip' in metadata:
            thread.client_ip = metadata['client_ip']
        if 'user_agent' in metadata:
            thread.user_agent = metadata['user_agent']
        
        # Start at first step
        first_step = self.config.get_step_by_order(workflow_type, 1)
        if first_step:
            thread.current_step = first_step['id']
        
        db.session.add(thread)
        db.session.commit()
        
        logger.info(f"Started workflow {workflow_type} thread={thread.id}")
        return thread
    
    def get_thread(self, thread_id: str, site_id: str) -> Optional[ConversationThread]:
        """Get conversation thread by ID with tenant isolation (REQUIRES site_id)"""
        thread = ConversationThread.query.filter_by(
            id=thread_id,
            site_id=site_id
        ).first()
        
        if thread:
            ensure_thread_integrity(thread)
        return thread
    
    def find_active_thread(self, site_id: str, session_id: str) -> Optional[ConversationThread]:
        """Find active thread for site/session"""
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id,
            workflow_status='active'
        ).order_by(ConversationThread.created_at.desc()).first()
        if thread:
            ensure_thread_integrity(thread)
        return thread
    
    # ============ WORKFLOW PROCESSING ============
    
    def process_message(
        self,
        thread: ConversationThread,
        user_message: str,
        site_id: str
    ) -> Dict[str, Any]:
        """
        Process user message in workflow.
        
        PURE FUNCTION - does not append messages, does not commit.
        Only updates thread fields and returns workflow result.
        MessageOrchestrator handles message appending and database persistence.
        
        Returns:
        {
            'reply': str,
            'workflow_state': str,  # next step
            'collected_data': dict,
            'workflow_status': str,  # "active", "completed", etc.
            'workflow_complete': bool,
            'should_escalate': bool
        }
        """
        
        # Current step config
        step_config = self.config.get_step(thread.workflow_type, thread.current_step)
        if not step_config:
            return {
                'reply': 'Workflow error: step not found',
                'workflow_status': 'error',
                'should_escalate': True
            }
        
        # Extract entities from message
        entities = extract_entities(user_message, site_id, use_llm=True)
        
        # Check if this step needs specific entity
        required_entity = step_config.get('entity')
        
        if required_entity and entities.get(required_entity):
            # Entity found - add to structured data
            thread.update_structured_data({required_entity: entities[required_entity]})
            
            # Get next step
            next_step_id = step_config.get('next_step')
            if next_step_id:
                thread.advance_workflow(next_step_id)
                next_step_config = self.config.get_step(thread.workflow_type, next_step_id)
            else:
                # Workflow complete
                next_step_config = None
        else:
            # Entity not found or not required
            if required_entity and step_config.get('required'):
                # Required entity missing - stay on step, ask again
                next_step_config = step_config
            else:
                # Optional entity or no entity needed - advance
                next_step_id = step_config.get('next_step')
                if next_step_id:
                    thread.advance_workflow(next_step_id)
                    next_step_config = self.config.get_step(thread.workflow_type, next_step_id)
                else:
                    next_step_config = None
        
        # Generate bot reply
        bot_reply = self._generate_reply(step_config or next_step_config, thread.structured_data)
        
        # Check if workflow should escalate
        should_escalate = thread.should_escalate()
        
        # Check if workflow complete
        workflow_complete = (next_step_config and next_step_config.get('final')) or \
                          (not next_step_config and thread.current_step and \
                           self.config.get_step(thread.workflow_type, thread.current_step).get('final'))
        
        if workflow_complete:
            thread.complete_workflow()
        
        # NOTE: No db.session.commit() here - orchestrator handles persistence
        
        return {
            'reply': bot_reply,
            'workflow_state': thread.current_step,
            'collected_data': thread.structured_data,
            'workflow_status': thread.workflow_status,
            'workflow_complete': workflow_complete,
            'should_escalate': should_escalate,
            'completion_score': thread.calculate_completion_score()
        }
    
    def _generate_reply(self, step_config: Dict[str, Any], collected_data: Dict[str, Any]) -> str:
        """
        Generate bot reply for step.
        
        Substitutes variables like {name}, {email} from collected_data.
        """
        if not step_config:
            return "Thank you! We're all set."
        
        template = step_config.get('ask', '')
        
        # Simple variable substitution
        for key, value in collected_data.items():
            placeholder = '{' + key + '}'
            template = template.replace(placeholder, str(value))
        
        return template
    
    # ============ WORKFLOW ANALYTICS ============
    
    def get_workflow_analytics(self, site_id: str, workflow_type: str, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for workflow.
        
        Returns:
        {
            'total_threads': int,
            'completion_rate': float,
            'avg_steps_to_completion': float,
            'escalation_rate': float,
            'avg_completion_score': float
        }
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        threads = ConversationThread.query.filter(
            ConversationThread.site_id == site_id,
            ConversationThread.workflow_type == workflow_type,
            ConversationThread.created_at >= cutoff_date
        ).all()
        
        if not threads:
            return {
                'total_threads': 0,
                'completion_rate': 0.0,
                'avg_steps_to_completion': 0,
                'escalation_rate': 0.0,
                'avg_completion_score': 0.0
            }
        
        completed = [t for t in threads if t.workflow_status == 'completed']
        escalated = [t for t in threads if t.escalation_triggered]
        
        return {
            'total_threads': len(threads),
            'completion_rate': len(completed) / len(threads) if threads else 0,
            'avg_steps_to_completion': sum(t.steps_completed for t in completed) / len(completed) if completed else 0,
            'escalation_rate': len(escalated) / len(threads) if threads else 0,
            'avg_completion_score': sum(t.completion_score for t in threads) / len(threads) if threads else 0,
            'abandoned_count': len([t for t in threads if t.workflow_status == 'abandoned']),
            'escalated_count': len(escalated)
        }
    
    # ============ WORKFLOW MANAGEMENT ============
    
    def list_active_workflows(self) -> list[str]:
        """List all active workflow types"""
        return list(self.config.get_enabled_workflows().keys())
    
    def get_workflow_metadata(self, workflow_type: str) -> Optional[Dict[str, Any]]:
        """Get workflow metadata (not steps, just info)"""
        config = self.config.get_workflow(workflow_type)
        if not config:
            return None
        
        return {
            'id': config.get('id'),
            'name': config.get('name'),
            'description': config.get('description'),
            'category': config.get('category'),
            'total_steps': len(config.get('steps', [])),
            'required_entities': config.get('required_entities', []),
            'version': config.get('version'),
            'enabled': config.get('enabled', True)
        }
    
    def reload_configs(self):
        """Reload workflow configs from disk (for live updates)"""
        self.config = get_workflow_config()
        logger.info("Reloaded workflow configurations")


# Global instance
_engine = None

def get_workflow_engine() -> GenericWorkflowEngine:
    """Get or create global workflow engine"""
    global _engine
    if _engine is None:
        _engine = GenericWorkflowEngine()
    return _engine
