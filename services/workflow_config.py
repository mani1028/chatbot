"""
Workflow Configuration Schema

This defines how workflows are built WITHOUT hardcoding FSM logic.
All workflows are now config-driven with:
- Step definitions
- Validation rules
- Entity mapping
- Conditional transitions
- Multi-language support
"""

import json
import os
from typing import Dict, List, Any, Optional

class WorkflowConfig:
    """
    Workflow configuration loader.
    
    Enables:
    - No code changes for new workflows
    - Admin-defined workflows
    - Blueprint workflows per vertical
    - Versioned workflow definitions
    """
    
    # Default workflows (built-in)
    BUILTIN_WORKFLOWS = {
        "booking": {
            "id": "booking",
            "name": "Service Booking",
            "description": "User books appointment/reservation",
            "category": "sales",
            "enabled": True,
            "version": "1.0",
            "steps": [
                {
                    "id": "greeting",
                    "order": 1,
                    "ask": "Hey there! I'd love to help you book {service}. What's your name?",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "collecting_service"
                },
                {
                    "id": "collecting_service",
                    "order": 2,
                    "ask": "What service are you interested in?",
                    "entity": "service",
                    "validation": "required",
                    "required": True,
                    "suggestions": ["haircut", "facial", "massage"],
                    "next_step": "collecting_name"
                },
                {
                    "id": "collecting_name",
                    "order": 3,
                    "ask": "May I get your name?",
                    "entity": "name",
                    "validation": "required",
                    "required": True,
                    "next_step": "collecting_email"
                },
                {
                    "id": "collecting_email",
                    "order": 4,
                    "ask": "What's your email?",
                    "entity": "email",
                    "validation": "email",
                    "required": True,
                    "next_step": "collecting_phone"
                },
                {
                    "id": "collecting_phone",
                    "order": 5,
                    "ask": "And your phone number?",
                    "entity": "phone",
                    "validation": "phone",
                    "required": True,
                    "next_step": "collecting_date"
                },
                {
                    "id": "collecting_date",
                    "order": 6,
                    "ask": "What date works for you? (e.g., tomorrow, March 15)",
                    "entity": "date",
                    "validation": "date",
                    "required": True,
                    "next_step": "collecting_time"
                },
                {
                    "id": "collecting_time",
                    "order": 7,
                    "ask": "What time? (e.g., 2pm)",
                    "entity": "time",
                    "validation": "time",
                    "required": True,
                    "next_step": "confirming"
                },
                {
                    "id": "confirming",
                    "order": 8,
                    "ask": "Perfect! Let me confirm:\n- Service: {service}\n- Name: {name}\n- Email: {email}\n- Phone: {phone}\n- Date: {date}\n- Time: {time}\n\nDoes this look right? (yes/no)",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "completed"
                },
                {
                    "id": "completed",
                    "order": 9,
                    "ask": "Your appointment is booked! We'll send a confirmation to {email}. Thank you!",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": None,
                    "final": True
                }
            ],
            "required_entities": ["service", "name", "email", "phone", "date", "time"],
            "escalation_triggers": {
                "max_unknown_intents": 3,
                "max_attempts_per_step": 5
            }
        },
        "lead_capture": {
            "id": "lead_capture",
            "name": "Lead Capture",
            "description": "Capture contact info and inquiry",
            "category": "marketing",
            "enabled": True,
            "version": "1.0",
            "steps": [
                {
                    "id": "greeting",
                    "order": 1,
                    "ask": "Thanks for your interest! I'd love to help.",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "collecting_name"
                },
                {
                    "id": "collecting_name",
                    "order": 2,
                    "ask": "May I have your name?",
                    "entity": "name",
                    "validation": "required",
                    "required": True,
                    "next_step": "collecting_email"
                },
                {
                    "id": "collecting_email",
                    "order": 3,
                    "ask": "Best email to reach you?",
                    "entity": "email",
                    "validation": "email",
                    "required": True,
                    "next_step": "collecting_phone"
                },
                {
                    "id": "collecting_phone",
                    "order": 4,
                    "ask": "How about your phone? (optional)",
                    "entity": "phone",
                    "validation": "phone",
                    "required": False,
                    "next_step": "collecting_message"
                },
                {
                    "id": "collecting_message",
                    "order": 5,
                    "ask": "What's your main interest or question?",
                    "entity": "message",
                    "validation": "required",
                    "required": True,
                    "next_step": "confirming"
                },
                {
                    "id": "confirming",
                    "order": 6,
                    "ask": "Thanks {name}! We'll reach out soon at {email}.",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "completed"
                },
                {
                    "id": "completed",
                    "order": 7,
                    "ask": "Great! We'll be in touch. Have a great day!",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": None,
                    "final": True
                }
            ],
            "required_entities": ["name", "email", "message"],
            "escalation_triggers": {
                "max_unknown_intents": 3,
                "max_attempts_per_step": 5
            }
        },
        "support": {
            "id": "support",
            "name": "Support Request",
            "description": "Route support issues with priority",
            "category": "support",
            "enabled": True,
            "version": "1.0",
            "steps": [
                {
                    "id": "greeting",
                    "order": 1,
                    "ask": "I'm sorry you're having an issue. I'm here to help!",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "collecting_issue"
                },
                {
                    "id": "collecting_issue",
                    "order": 2,
                    "ask": "Can you describe the issue you're facing?",
                    "entity": "issue",
                    "validation": "required",
                    "required": True,
                    "next_step": "collecting_priority"
                },
                {
                    "id": "collecting_priority",
                    "order": 3,
                    "ask": "How urgent is this? (normal, high, urgent)",
                    "entity": "priority",
                    "validation": "required",
                    "required": True,
                    "suggestions": ["normal", "high", "urgent"],
                    "next_step": "collecting_contact"
                },
                {
                    "id": "collecting_contact",
                    "order": 4,
                    "ask": "Best way to reach you? (email or phone)",
                    "entity": "contact",
                    "validation": "required",
                    "required": True,
                    "next_step": "confirming"
                },
                {
                    "id": "confirming",
                    "order": 5,
                    "ask": "Got it! Issue: {issue}\nPriority: {priority}\n\nWe'll get back to you shortly.",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": "completed"
                },
                {
                    "id": "completed",
                    "order": 6,
                    "ask": "Thank you! A support specialist will contact you soon.",
                    "entity": None,
                    "validation": None,
                    "required": False,
                    "next_step": None,
                    "final": True
                }
            ],
            "required_entities": ["issue", "priority", "contact"],
            "escalation_triggers": {
                "max_unknown_intents": 2,
                "max_attempts_per_step": 3,
                "escalate_on_urgent": True
            }
        }
    }
    
    def __init__(self, custom_workflows_dir: Optional[str] = None):
        """
        Initialize workflow config loader.
        
        Args:
            custom_workflows_dir: Directory with custom .json workflow files
        """
        self.workflows = {}
        self._load_builtin()
        if custom_workflows_dir:
            self._load_custom(custom_workflows_dir)
    
    def _load_builtin(self):
        """Load built-in workflows"""
        self.workflows = self.BUILTIN_WORKFLOWS.copy()
    
    def _load_custom(self, directory: str):
        """Load custom workflow files from directory"""
        if not os.path.exists(directory):
            return
        
        for filename in os.listdir(directory):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    workflow = json.load(f)
                    workflow_id = workflow.get('id', filename.replace('.json', ''))
                    self.workflows[workflow_id] = workflow
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading workflow {filename}: {e}")
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow configuration by ID"""
        return self.workflows.get(workflow_id)
    
    def get_step(self, workflow_id: str, step_id: str) -> Optional[Dict[str, Any]]:
        """Get specific step in workflow"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        for step in workflow.get('steps', []):
            if step['id'] == step_id:
                return step
        
        return None
    
    def get_next_step(self, workflow_id: str, current_step_id: str) -> Optional[str]:
        """Get next step ID based on current step"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        for step in workflow.get('steps', []):
            if step['id'] == current_step_id:
                return step.get('next_step')
        
        return None
    
    def get_step_by_order(self, workflow_id: str, order: int) -> Optional[Dict[str, Any]]:
        """Get step by order number"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        for step in workflow.get('steps', []):
            if step['order'] == order:
                return step
        
        return None
    
    def get_first_step(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get first step of workflow"""
        return self.get_step_by_order(workflow_id, 1)
    
    def get_all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Get all available workflows"""
        return self.workflows.copy()
    
    def get_enabled_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Get only enabled workflows"""
        return {
            wid: w for wid, w in self.workflows.items()
            if w.get('enabled', True)
        }
    
    def list_workflow_ids(self) -> List[str]:
        """List all workflow IDs"""
        return list(self.workflows.keys())
    
    def validate_step_config(self, step: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate step configuration.
        
        Returns: (is_valid, error_message)
        """
        required_fields = ['id', 'order', 'ask']
        
        for field in required_fields:
            if field not in step:
                return False, f"Missing required field: {field}"
        
        if not isinstance(step['order'], int) or step['order'] < 1:
            return False, "order must be positive integer"
        
        return True, None


# Global config instance
_workflow_config = None

def get_workflow_config() -> WorkflowConfig:
    """Get or create global workflow config instance"""
    global _workflow_config
    if _workflow_config is None:
        custom_dir = os.path.join(
            os.path.dirname(__file__),
            '..',
            'workflow_configs'  # Directory for custom workflows
        )
        _workflow_config = WorkflowConfig(custom_dir)
    return _workflow_config
