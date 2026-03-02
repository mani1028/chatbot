"""
Form Service - Handles multi-step form processing during conversations.
Works with ConversationState to track progress through form fields.
"""
import json
import logging
from datetime import datetime
from database import db
from models.form import FormDefinition, FormSubmission
from models.conversation_state import ConversationState
from services.webhook_service import fire_event, EVENT_FORM_COMPLETE

logger = logging.getLogger(__name__)


def get_form_for_intent(site_id: int, intent_id: int) -> FormDefinition:
    """Find an active form linked to an intent."""
    return FormDefinition.query.filter_by(
        site_id=site_id,
        intent_id=intent_id,
        is_active=True
    ).first()


def start_form(state: ConversationState, form: FormDefinition) -> dict:
    """
    Start a form flow. Returns the first question prompt.
    """
    state.flow_type = 'form'
    state.form_id = form.id
    state.form_step_index = 0
    state.active_intent = f'form_{form.name}'
    state.current_step = 'collecting'
    state.set_collected_data({})
    db.session.commit()

    first_step = form.get_step(0)
    if not first_step:
        return {'text': form.completion_message, 'form_complete': True}

    step_count = form.step_count()
    return {
        'text': first_step.get('prompt', 'Please provide the information:'),
        'form_active': True,
        'form_name': form.name,
        'current_field': first_step.get('field', ''),
        'field_type': first_step.get('type', 'text'),
        'step': 1,
        'total_steps': step_count,
        'required': first_step.get('required', False)
    }


def process_form_input(state: ConversationState, user_input: str) -> dict:
    """
    Process user input for the current form step.
    Returns next question, validation error, or completion message.
    """
    form = db.session.get(FormDefinition, state.form_id)
    if not form:
        state.clear_flow()
        db.session.commit()
        return {'text': 'Form not found. How else can I help?', 'form_active': False}

    current_step = form.get_step(state.form_step_index)
    if not current_step:
        return _complete_form(state, form)

    # Handle skip commands
    if user_input.strip().lower() in ('skip', 'next') and not current_step.get('required', False):
        return _advance_form(state, form, current_step.get('field'), None)

    # Handle cancel commands
    if user_input.strip().lower() in ('cancel', 'quit', 'stop', 'exit'):
        state.clear_flow()
        db.session.commit()
        return {
            'text': 'Form cancelled. How else can I help you?',
            'form_active': False
        }

    # Validate the input
    is_valid, error_msg = form.validate_field(current_step, user_input)
    if not is_valid:
        return {
            'text': error_msg,
            'form_active': True,
            'form_name': form.name,
            'current_field': current_step.get('field', ''),
            'field_type': current_step.get('type', 'text'),
            'step': state.form_step_index + 1,
            'total_steps': form.step_count(),
            'validation_error': True
        }

    # Valid input - save and advance
    return _advance_form(state, form, current_step.get('field'), user_input.strip())


def _advance_form(state: ConversationState, form: FormDefinition, field_name: str, value) -> dict:
    """Save field value and advance to next step."""
    # Save the field
    if field_name and value is not None:
        state.add_collected_field(field_name, value)

    # Move to next step
    state.form_step_index += 1
    next_step = form.get_step(state.form_step_index)

    if next_step is None:
        # All fields collected — complete the form
        return _complete_form(state, form)

    db.session.commit()

    return {
        'text': next_step.get('prompt', 'Please continue:'),
        'form_active': True,
        'form_name': form.name,
        'current_field': next_step.get('field', ''),
        'field_type': next_step.get('type', 'text'),
        'step': state.form_step_index + 1,
        'total_steps': form.step_count(),
        'required': next_step.get('required', False)
    }


def _complete_form(state: ConversationState, form: FormDefinition) -> dict:
    """Handle form completion - save submission, trigger webhooks."""
    collected = state.get_collected_data()

    # Save the submission record
    submission = FormSubmission(
        site_id=state.site_id,
        form_id=form.id,
        session_id=state.session_id,
        status='completed'
    )
    submission.set_data(collected)
    db.session.add(submission)

    # Save as lead if configured
    if form.save_as_lead:
        _save_as_lead(state.site_id, state.session_id, collected)

    # Clear the form flow
    state.clear_flow()
    db.session.commit()

    # Fire webhook event (background)
    fire_event(state.site_id, EVENT_FORM_COMPLETE, {
        'form_name': form.name,
        'form_id': form.id,
        'session_id': state.session_id,
        'data': collected
    })

    return {
        'text': form.completion_message or 'Thank you! Your information has been submitted.',
        'form_active': False,
        'form_complete': True,
        'submission_id': submission.id if submission.id else None
    }


def _save_as_lead(site_id: int, session_id: str, data: dict):
    """Save form data as a LeadCapture record if name+email present."""
    try:
        from models.lead_capture import LeadCapture

        name = data.get('name', data.get('full_name', data.get('user_name', '')))
        email = data.get('email', data.get('user_email', ''))

        if not name or not email:
            return  # Can't create lead without name+email

        phone = data.get('phone', data.get('user_phone', ''))
        context = json.dumps({k: v for k, v in data.items() if k not in ('name', 'email', 'phone', 'full_name', 'user_name', 'user_email', 'user_phone')})

        lead = LeadCapture(
            site_id=site_id,
            session_id=session_id or '',
            user_name=name,
            user_email=email,
            user_phone=phone,
            question_context=context
        )
        db.session.add(lead)
        db.session.commit()
        logger.info(f"Lead saved from form for site {site_id}")
    except Exception as e:
        logger.error(f"Failed to save form lead: {e}")
        db.session.rollback()
