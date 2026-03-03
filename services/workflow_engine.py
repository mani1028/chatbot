"""
Conversation State Machine (FSM) Handler
Manages workflow transitions and multi-step conversations.
Supports: Booking, Lead Capture, Support Escalation, etc.
"""
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Callable, Optional
from models.conversation_state import ConversationState
from services.entity_extractor import extract_entities

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============ BOOKING WORKFLOW FSM ============
class BookingState(Enum):
    """Finite states for booking workflow."""
    IDLE = "idle"
    GREETING = "greeting"
    COLLECTING_SERVICE = "collecting_service"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_EMAIL = "collecting_email"
    COLLECTING_PHONE = "collecting_phone"
    COLLECTING_DATE = "collecting_date"
    COLLECTING_TIME = "collecting_time"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BookingWorkflow:
    """State machine for booking appointments."""
    
    # Define transitions and prompts for each state
    TRANSITIONS = {
        BookingState.GREETING: {
            "next_state": BookingState.COLLECTING_SERVICE,
            "prompt": "Great! What service would you like to book? (e.g., consultation, haircut, meeting)",
            "required_entities": [],
            "optional_entities": []
        },
        BookingState.COLLECTING_SERVICE: {
            "next_state": BookingState.COLLECTING_NAME,
            "prompt": "Perfect! May I have your name please?",
            "required_entities": ["service"],
            "optional_entities": []
        },
        BookingState.COLLECTING_NAME: {
            "next_state": BookingState.COLLECTING_EMAIL,
            "prompt": "Thanks {name}! What's your email address?",
            "required_entities": ["name"],
            "optional_entities": []
        },
        BookingState.COLLECTING_EMAIL: {
            "next_state": BookingState.COLLECTING_PHONE,
            "prompt": "Got it! And your phone number?",
            "required_entities": ["email"],
            "optional_entities": []
        },
        BookingState.COLLECTING_PHONE: {
            "next_state": BookingState.COLLECTING_DATE,
            "prompt": "Perfect! What date would you prefer? (e.g., tomorrow, March 5, next Monday)",
            "required_entities": ["phone"],
            "optional_entities": []
        },
        BookingState.COLLECTING_DATE: {
            "next_state": BookingState.COLLECTING_TIME,
            "prompt": "What time works best for you? (e.g., 2:00 PM, 9:30 AM)",
            "required_entities": ["date"],
            "optional_entities": []
        },
        BookingState.COLLECTING_TIME: {
            "next_state": BookingState.CONFIRMING,
            "prompt": "",  # Will build confirmation message
            "required_entities": ["time"],
            "optional_entities": []
        },
        BookingState.CONFIRMING: {
            "next_state": BookingState.COMPLETED,
            "prompt": "Does this look correct? Please confirm yes/no.",
            "required_entities": [],
            "optional_entities": []
        },
        BookingState.COMPLETED: {
            "next_state": None,
            "prompt": "[CONFIRMED] Your booking is confirmed! You'll receive a confirmation email shortly.",
            "required_entities": [],
            "optional_entities": []
        }
    }
    
    @staticmethod
    def start(state_obj: ConversationState) -> Dict[str, Any]:
        """Initialize booking workflow."""
        logger.info(f"Starting booking workflow for session {state_obj.session_id}")
        
        state_obj.active_intent = "booking"
        state_obj.current_step = BookingState.GREETING.value
        state_obj.set_collected_data({})
        state_obj.update_context(workflow_started=datetime.utcnow().isoformat())
        
        from database import db
        db.session.commit()
        
        greeting = "Hello! Welcome to our booking system. I'll help you schedule an appointment."
        return {
            "text": greeting,
            "intent_name": "booking_greeting",
            "intent_type": "INFO",
            "requires_confirmation": False,
            "next_expected": "service"
        }
    
    @staticmethod
    def handle_message(state_obj: ConversationState, message: str, site_id: int) -> Dict[str, Any]:
        """Process user message in booking workflow."""
        from database import db
        
        current_state = BookingState(state_obj.current_step)
        logger.info(f"Booking workflow - current state: {current_state.value}, message: {message[:50]}...")
        
        # Extract entities from message
        entities = extract_entities(message, site_id=site_id)
        logger.debug(f"Extracted entities: {entities}")
        
        # Update collected data
        collected = state_obj.get_collected_data()
        collected.update(entities)
        state_obj.set_collected_data(collected)
        
        # Get transition info
        transition = BookingWorkflow.TRANSITIONS[current_state]
        required_entities = transition.get("required_entities", [])
        
        # Check if we have required entities to move to next state
        has_required = all(req in collected for req in required_entities)
        
        if not has_required:
            # Ask again for missing required entity
            missing = [r for r in required_entities if r not in collected]
            logger.debug(f"Missing required entities: {missing}")
            
            return {
                "text": f"I need your {missing[0]} to proceed. Could you please provide it?",
                "intent_name": "booking_collect_entity",
                "intent_type": "INFO",
                "state": current_state.value,
                "missing_entity": missing[0],
                "collected_so_far": collected
            }
        
        # Move to next state
        next_state = transition.get("next_state")
        if next_state is None:
            # Workflow complete
            state_obj.current_step = BookingState.COMPLETED.value
            db.session.commit()
            
            return {
                "text": transition["prompt"],
                "intent_name": "booking_completed",
                "intent_type": "INFO",
                "state": "completed",
                "collected_data": collected
            }
        
        state_obj.current_step = next_state.value
        db.session.commit()
        
        # Get prompt for next state, with entity interpolation
        next_transition = BookingWorkflow.TRANSITIONS[next_state]
        prompt = next_transition["prompt"]
        
        # Interpolate collected data into prompt
        for key, value in collected.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        
        logger.info(f"Transitioning to {next_state.value}")
        
        return {
            "text": prompt,
            "intent_name": "booking_progress",
            "intent_type": "INFO",
            "state": next_state.value,
            "collected_so_far": collected
        }
    
    @staticmethod
    def confirm(state_obj: ConversationState, confirmation: str) -> Dict[str, Any]:
        """Handle confirmation in CONFIRMING state."""
        from database import db
        
        if confirmation.lower() in ['yes', 'y', 'confirm', 'correct']:
            state_obj.current_step = BookingState.COMPLETED.value
            state_obj.update_context(confirmed_at=datetime.utcnow().isoformat())
            db.session.commit()
            
            collected = state_obj.get_collected_data()
            return {
                "text": "[CONFIRMED] Your booking is confirmed! You'll receive a confirmation email at {email} shortly.".format(**collected),
                "intent_name": "booking_confirmed",
                "intent_type": "INFO",
                "state": "completed",
                "booking_data": collected,
                "success": True
            }
        else:
            # Go back to collecting
            state_obj.current_step = BookingState.COLLECTING_SERVICE.value
            state_obj.set_collected_data({})
            db.session.commit()
            
            return {
                "text": "No problem! Let's start over. What service would you like to book?",
                "intent_name": "booking_restart",
                "intent_type": "INFO",
                "state": "collecting_service"
            }


# ============ LEAD CAPTURE WORKFLOW FSM ============
class LeadCaptureState(Enum):
    """Finite states for lead capture workflow."""
    IDLE = "idle"
    GREETING = "greeting"
    COLLECTING_NAME = "collecting_name"
    COLLECTING_EMAIL = "collecting_email"
    COLLECTING_PHONE = "collecting_phone"
    COLLECTING_MESSAGE = "collecting_message"
    CONFIRMING = "confirming"
    COMPLETED = "completed"


class LeadCaptureWorkflow:
    """State machine for capturing lead information."""
    
    TRANSITIONS = {
        LeadCaptureState.GREETING: {
            "next_state": LeadCaptureState.COLLECTING_NAME,
            "prompt": "Thank you for your interest! What's your name?",
            "required_entities": [],
            "optional_entities": []
        },
        LeadCaptureState.COLLECTING_NAME: {
            "next_state": LeadCaptureState.COLLECTING_EMAIL,
            "prompt": "Nice to meet you! What's your email address?",
            "required_entities": ["name"],
            "optional_entities": []
        },
        LeadCaptureState.COLLECTING_EMAIL: {
            "next_state": LeadCaptureState.COLLECTING_PHONE,
            "prompt": "Thank you. Could you also share your phone number?",
            "required_entities": ["email"],
            "optional_entities": []
        },
        LeadCaptureState.COLLECTING_PHONE: {
            "next_state": LeadCaptureState.COLLECTING_MESSAGE,
            "prompt": "Great! Now, how can we help you? Please describe your needs.",
            "required_entities": ["phone"],
            "optional_entities": []
        },
        LeadCaptureState.COLLECTING_MESSAGE: {
            "next_state": LeadCaptureState.CONFIRMING,
            "prompt": "Perfect! Let me confirm the information before we proceed.",
            "required_entities": ["message"],
            "optional_entities": []
        },
        LeadCaptureState.CONFIRMING: {
            "next_state": LeadCaptureState.COMPLETED,
            "prompt": "Does everything look correct?",
            "required_entities": [],
            "optional_entities": []
        }
    }

    @staticmethod
    def start(state_obj: ConversationState) -> Dict[str, Any]:
        """Start lead capture workflow."""
        state_obj.active_intent = 'lead_capture'
        state_obj.current_step = LeadCaptureState.GREETING.value
        state_obj.set_collected_data({})
        state_obj.update_context(workflow_started=datetime.now().isoformat())
        from database import db
        db.session.commit()
        
        return {
            "text": "Thank you for your interest! I'd like to gather some information. What's your name?",
            "intent_name": "lead_capture_start",
            "intent_type": "INFO",
            "state": "greeting",
            "collected_so_far": {}
        }

    @staticmethod
    def handle_message(state_obj: ConversationState, message: str, site_id: int) -> Dict[str, Any]:
        """Process message in lead capture workflow."""
        logger.info(f"Lead capture workflow - current state: {state_obj.current_step}, message: {message}...")
        
        # Extract entities from message
        entities = extract_entities(message, site_id=site_id)
        logger.debug(f"Extracted entities: {entities}")
        
        # Get current state info
        current_state = LeadCaptureState(state_obj.current_step)
        transition_info = LeadCaptureWorkflow.TRANSITIONS.get(current_state)
        
        if not transition_info:
            return {"text": "Workflow configuration error.", "intent_name": "error", "intent_type": "ERROR"}
        
        # Update collected data with current entities
        collected = state_obj.get_collected_data()
        collected.update(entities)
        
        # Check if we have required entities
        for req_entity in transition_info.get('required_entities', []):
            if req_entity not in collected and req_entity != 'message':
                # Special handling for 'message' field - accept entire message as content
                return {
                    "text": f"I need your {req_entity} to proceed. Could you please provide it?",
                    "intent_name": "lead_capture_collecting",
                    "intent_type": "INFO",
                    "state": state_obj.current_step,
                    "collected_so_far": collected
                }
        
        # If collecting message, treat the entire message as the content
        if current_state == LeadCaptureState.COLLECTING_MESSAGE:
            entities['message'] = message[:500]  # Store user's message as lead message
        
        # Update collected data
        collected = state_obj.get_collected_data()
        collected.update(entities)
        state_obj.set_collected_data(collected)
        
        # Advance state
        next_state = transition_info.get('next_state')
        state_obj.current_step = next_state.value
        
        from database import db
        db.session.commit()
        
        logger.info(f"Transitioning to {next_state.value}")
        
        # Get next prompt
        next_transition = LeadCaptureWorkflow.TRANSITIONS.get(next_state)
        if next_transition:
            return {
                "text": next_transition.get('prompt', 'Next step...'),
                "intent_name": "lead_capture_progress",
                "intent_type": "INFO",
                "state": next_state.value,
                "collected_so_far": collected
            }
        elif next_state == LeadCaptureState.COMPLETED:
            return {
                "text": "[CONFIRMED] Lead captured successfully! We'll be in touch shortly.",
                "intent_name": "lead_capture_completed",
                "intent_type": "INFO",
                "state": "completed",
                "lead_data": collected,
                "success": True
            }
        else:
            return {
                "text": "Thank you! We have your information.",
                "intent_name": "lead_capture_done",
                "intent_type": "INFO",
                "state": next_state.value,
                "collected_so_far": collected
            }


# ============ SUPPORT ESCALATION WORKFLOW FSM ============
class SupportState(Enum):
    """Finite states for support escalation workflow."""
    IDLE = "idle"
    GREETING = "greeting"
    COLLECTING_ISSUE = "collecting_issue"
    COLLECTING_PRIORITY = "collecting_priority"
    COLLECTING_CONTACT = "collecting_contact"
    CONFIRMING = "confirming"
    ESCALATED = "escalated"


class SupportWorkflow:
    """State machine for support ticket escalation."""
    
    TRANSITIONS = {
        SupportState.GREETING: {
            "next_state": SupportState.COLLECTING_ISSUE,
            "prompt": "I'm sorry to hear you're experiencing an issue. Can you describe what's happening?",
            "required_entities": [],
            "optional_entities": []
        },
        SupportState.COLLECTING_ISSUE: {
            "next_state": SupportState.COLLECTING_PRIORITY,
            "prompt": "Thank you for explaining. How urgent is this issue? (low/medium/high/critical)",
            "required_entities": [],
            "optional_entities": []
        },
        SupportState.COLLECTING_PRIORITY: {
            "next_state": SupportState.COLLECTING_CONTACT,
            "prompt": "Got it. What's the best way to reach you? (phone or email)",
            "required_entities": [],
            "optional_entities": []
        },
        SupportState.COLLECTING_CONTACT: {
            "next_state": SupportState.CONFIRMING,
            "prompt": "Perfect. Let me confirm your contact information.",
            "required_entities": [],
            "optional_entities": []
        },
        SupportState.CONFIRMING: {
            "next_state": SupportState.ESCALATED,
            "prompt": "Does everything look correct?",
            "required_entities": [],
            "optional_entities": []
        }
    }

    @staticmethod
    def start(state_obj: ConversationState) -> Dict[str, Any]:
        """Start support escalation workflow."""
        state_obj.active_intent = 'support_escalation'
        state_obj.current_step = SupportState.GREETING.value
        state_obj.set_collected_data({})
        state_obj.update_context(workflow_started=datetime.now().isoformat())
        from database import db
        db.session.commit()
        
        return {
            "text": "I'm here to help! I'm sorry to hear you're experiencing an issue. Can you describe what's happening?",
            "intent_name": "support_start",
            "intent_type": "INFO",
            "state": "greeting",
            "collected_so_far": {}
        }

    @staticmethod
    def handle_message(state_obj: ConversationState, message: str, site_id: int) -> Dict[str, Any]:
        """Process message in support workflow."""
        logger.info(f"Support workflow - current state: {state_obj.current_step}, message: {message}...")
        
        # Extract entities
        entities = extract_entities(message, site_id=site_id)
        logger.debug(f"Extracted entities: {entities}")
        
        current_state = SupportState(state_obj.current_step)
        transition_info = SupportWorkflow.TRANSITIONS.get(current_state)
        
        if not transition_info:
            return {"text": "Workflow configuration error.", "intent_name": "error", "intent_type": "ERROR"}
        
        # Collect issue description if in COLLECTING_ISSUE state
        if current_state == SupportState.COLLECTING_ISSUE:
            entities['issue'] = message[:1000]
        
        # Collect priority if mentioned
        priority_keywords = ['low', 'medium', 'high', 'critical', 'urgent']
        for keyword in priority_keywords:
            if keyword in message.lower():
                entities['priority'] = keyword
                break
        
        # Update collected data
        collected = state_obj.get_collected_data()
        collected.update(entities)
        state_obj.set_collected_data(collected)
        
        # Advance state
        next_state = transition_info.get('next_state')
        state_obj.current_step = next_state.value
        
        from database import db
        db.session.commit()
        
        logger.info(f"Transitioning to {next_state.value}")
        
        # Get next prompt
        next_transition = SupportWorkflow.TRANSITIONS.get(next_state)
        if next_transition:
            return {
                "text": next_transition.get('prompt', 'Next step...'),
                "intent_name": "support_progress",
                "intent_type": "INFO",
                "state": next_state.value,
                "collected_so_far": collected
            }
        elif next_state == SupportState.ESCALATED:
            return {
                "text": "[CONFIRMED] Your support ticket has been escalated. A team member will contact you shortly.",
                "intent_name": "support_escalated",
                "intent_type": "HUMAN",
                "state": "escalated",
                "ticket_data": collected,
                "handoff": True
            }
        else:
            return {
                "text": "Thank you for your information. We're working on your issue.",
                "intent_name": "support_progress",
                "intent_type": "INFO",
                "state": next_state.value,
                "collected_so_far": collected
            }


class WorkflowManager:
    """Manages different workflow types."""
    
    WORKFLOWS = {
        "booking": BookingWorkflow,
        "lead_capture": LeadCaptureWorkflow,
        "support_escalation": SupportWorkflow,
    }
    
    @staticmethod
    def start_workflow(workflow_type: str, state_obj: ConversationState, site_id: int) -> Dict[str, Any]:
        """Start a workflow."""
        workflow_class = WorkflowManager.WORKFLOWS.get(workflow_type)
        if not workflow_class:
            return {"error": f"Unknown workflow type: {workflow_type}"}
        
        return workflow_class.start(state_obj)
    
    @staticmethod
    def handle_workflow_message(state_obj: ConversationState, message: str, site_id: int) -> Dict[str, Any]:
        """Process message in active workflow."""
        workflow_type = state_obj.active_intent
        workflow_class = WorkflowManager.WORKFLOWS.get(workflow_type)
        
        if not workflow_class:
            return {"error": f"Unknown workflow: {workflow_type}"}
        
        return workflow_class.handle_message(state_obj, message, site_id)
    
    @staticmethod
    def is_in_workflow(state_obj: Optional[ConversationState]) -> bool:
        """Check if session is in active workflow."""
        if not state_obj:
            return False
        if state_obj.is_expired():
            return False
        if not state_obj.active_intent:
            return False
        return state_obj.active_intent in WorkflowManager.WORKFLOWS
