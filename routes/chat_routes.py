from flask import Blueprint, request, jsonify
from models.site import Site
from models.usage import Usage
from models.plan import Plan, Subscription
from services.chat_service import process_message
from database import db, limiter
from datetime import datetime
from models import LeadCapture, ContactRequest
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models.chat_log import ChatLog

# Define Blueprint (ONLY ONCE)
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

# Lead capture endpoint
@chat_bp.route('/lead-capture', methods=['POST'])
@limiter.limit("10 per minute")
def lead_capture():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    public_key = data.get('site_key')
    session_id = data.get('session_id')
    user_message = data.get('user_message', '')
    if not (name and email and public_key):
        return jsonify({'error': 'Missing required fields'}), 400
    site = Site.query.filter_by(public_key=public_key).first()
    if not site:
        return jsonify({'error': 'Invalid Site Key'}), 403
    
    # Safely map database columns dynamically based on what exists
    kwargs = {'site_id': site.id}
    
    if hasattr(LeadCapture, 'user_name'):
        kwargs['user_name'] = name
        kwargs['user_email'] = email
        kwargs['user_phone'] = phone
    else:
        kwargs['name'] = name
        kwargs['email'] = email
        kwargs['phone'] = phone
        
    if hasattr(LeadCapture, 'session_id'):
        kwargs['session_id'] = session_id
        
    if hasattr(LeadCapture, 'question_context'):
        kwargs['question_context'] = user_message
    elif hasattr(LeadCapture, 'message'):
        kwargs['message'] = user_message
    elif hasattr(LeadCapture, 'context'):
        kwargs['context'] = user_message

    lead = LeadCapture(**kwargs)
    db.session.add(lead)
    db.session.commit()
    return jsonify({'ok': True})

def get_request_domain():
    referer = request.headers.get('Referer', '')
    if referer:
        from urllib.parse import urlparse
        domain = urlparse(referer).netloc
        return domain
    return request.headers.get('Host', '').split(':')[0]

@chat_bp.route('/test', methods=['POST'])
def send_message_test():
    """
    INTERNAL TESTING ENDPOINT (no rate limiting).
    Use this endpoint only for deployment validation tests.
    This endpoint bypasses rate limiting to measure raw server performance.
    
    In production, this endpoint should be removed or restricted to localhost.
    """
    from app import socketio
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    public_key = data.get('site_key')
    message = data.get('message')
    session_id = data.get('session_id')
    page_url = data.get('page_url')

    if not public_key:
        return jsonify({'error': 'Missing site_key parameter'}), 400
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    site = Site.query.filter_by(public_key=public_key).first()
    if not site:
        return jsonify({'error': 'Invalid Site Key'}), 403

    from models.client_config import ClientConfig
    config_map = {c.key: c.value for c in ClientConfig.query.filter_by(site_id=site.id).all()}

    usage_limit = int(config_map.get('max_monthly_chats', site.plan.max_monthly_chats if site.plan else 1000))
    now = datetime.utcnow()
    month_str = now.strftime('%Y-%m')
    usage = Usage.query.filter_by(site_id=site.id, month=month_str).first()
    if not usage:
        usage = Usage(site_id=site.id, month=month_str, messages=1)
        db.session.add(usage)
    else:
        usage.messages += 1
    db.session.commit()

    # ⚠️ TEST ENDPOINT: Skip domain validation for internal testing
    # This allows load testing without full production validation
    # In production deployment, REMOVE THIS ENDPOINT

    try:
        response = process_message(site.id, message, session_id, page_url=page_url)
        # Emit Socket.IO events for live agent handoff
        handoff = False
        if hasattr(response, 'handoff'):
            handoff = response.handoff
        elif isinstance(response, dict) and response.get('handoff'):
            handoff = response.get('handoff')
        if handoff:
            # Notify the agent dashboard room for this specific site
            socketio.emit('agent_alert', {
                'site_id': site.id,
                'session_id': session_id,
                'message': 'A user is requesting human assistance!',
                'page_url': page_url
            }, room=f"admin_site_{site.id}")
            # Notify the user's widget that a human was pinged
            socketio.emit('agent_handoff', {
                'status': 'connecting'
            }, room=session_id)
        if hasattr(response, 'to_dict'):
            return jsonify(response.to_dict()), 200
        return jsonify(response), 200
    except Exception as e:
        print(f"Error processing message: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@chat_bp.route('', methods=['POST'])
@limiter.limit("10/minute;100/hour")
def send_message():
    from app import socketio
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    public_key = data.get('site_key')
    message = data.get('message')
    session_id = data.get('session_id')
    page_url = data.get('page_url')

    if not public_key:
        return jsonify({'error': 'Missing site_key parameter'}), 400
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    site = Site.query.filter_by(public_key=public_key).first()
    if not site:
        return jsonify({'error': 'Invalid Site Key'}), 403

    from models.client_config import ClientConfig
    config_map = {c.key: c.value for c in ClientConfig.query.filter_by(site_id=site.id).all()}

    usage_limit = int(config_map.get('max_monthly_chats', site.plan.max_monthly_chats if site.plan else 1000))
    now = datetime.utcnow()
    month_str = now.strftime('%Y-%m')
    usage = Usage.query.filter_by(site_id=site.id, month=month_str).first()
    if not usage:
        usage = Usage(site_id=site.id, month=month_str, messages=1)
        db.session.add(usage)
    else:
        usage.messages += 1
    db.session.commit()

    # Use the helper function to extract the domain correctly
    request_domain = get_request_domain()
    allowed_domains = config_map.get('allowed_domains')
    if allowed_domains:
        allowed_domains_list = [d.strip() for d in allowed_domains.split(',') if d.strip()]
        if request_domain not in allowed_domains_list:
            return jsonify({'error': 'Unauthorized domain'}), 403
    else:
        if not site.is_domain_allowed(request_domain):
            return jsonify({'error': 'Unauthorized domain'}), 403

    try:
        response = process_message(site.id, message, session_id, page_url=page_url)
        # Emit Socket.IO events for live agent handoff
        handoff = False
        if hasattr(response, 'handoff'):
            handoff = response.handoff
        elif isinstance(response, dict) and response.get('handoff'):
            handoff = response.get('handoff')
        if handoff:
            # Notify the agent dashboard room for this specific site
            socketio.emit('agent_alert', {
                'site_id': site.id,
                'session_id': session_id,
                'message': 'A user is requesting human assistance!',
                'page_url': page_url
            }, room=f"admin_site_{site.id}")
            # Notify the user's widget that a human was pinged
            socketio.emit('agent_handoff', {
                'status': 'connecting'
            }, room=session_id)
        if hasattr(response, 'to_dict'):
            return jsonify(response.to_dict()), 200
        return jsonify(response), 200
    except Exception as e:
        print(f"Error processing message: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@chat_bp.route('/history', methods=['GET'])
def get_chat_history():
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify([])

    # Fetch the last 50 messages for this session, ordered chronologically
    logs = ChatLog.query.filter_by(session_id=session_id).order_by(ChatLog.created_at.asc()).limit(50).all()

    # If no logs, return empty list
    if not logs:
        return jsonify([]), 200
    
    # Get site_id from the first log entry
    site_id = logs[0].site_id
    
    # Check if chat history preservation is enabled for this site
    from models.client_config import ClientConfig
    preserve_chat_history = ClientConfig.query.filter_by(
        site_id=site_id,
        key='preserve_chat_history'
    ).first()
    
    # If preserve_chat_history is "off", return empty list (no history shown)
    if preserve_chat_history and preserve_chat_history.value == 'off':
        return jsonify([]), 200

    history = []
    for log in logs:
        # Format for the frontend
        history.append({
            'text': log.user_message,
            'sender': 'user'
        })
        if log.bot_response:
            history.append({
                'text': log.bot_response,
                'sender': 'bot'
            })

    # Ensure the response is always an array
    return jsonify(history if history else []), 200


# Contact agent endpoint to submit contact requests
@chat_bp.route('/contact-agent', methods=['POST'])
@limiter.limit("20 per hour")
def submit_contact_request():
    """
    Submit a contact request to reach out to an agent.
    
    Request JSON:
    {
        "site_key": "public_key_here",
        "session_id": "session_id",
        "user_name": "John Doe",
        "user_email": "john@example.com",
        "message": "I need to speak with an agent",
        "priority": "normal" (low, normal, high, urgent)
    }
    """
    data = request.get_json()
    
    # Validate required fields
    user_name = data.get('user_name', '').strip()
    user_email = data.get('user_email', '').strip()
    message = data.get('message', '').strip()
    priority = data.get('priority', 'normal').lower()
    public_key = data.get('site_key')
    session_id = data.get('session_id')
    
    if not all([user_name, user_email, message, public_key]):
        return jsonify({'error': 'Missing required fields: user_name, user_email, message, site_key'}), 400
    
    # Validate priority
    if priority not in ['low', 'normal', 'high', 'urgent']:
        priority = 'normal'
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, user_email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    # Get site
    site = Site.query.filter_by(public_key=public_key).first()
    if not site:
        return jsonify({'error': 'Invalid Site Key'}), 403
    
    # Create contact request
    contact_request = ContactRequest(
        site_id=site.id,
        session_id=session_id,
        user_name=user_name,
        user_email=user_email,
        message=message,
        priority=priority,
        status='new'
    )
    
    try:
        db.session.add(contact_request)
        db.session.commit()
        return jsonify({
            'ok': True,
            'message': 'Your request has been submitted. An agent will contact you shortly.',
            'request_id': contact_request.id
        }), 200
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Failed to create contact request: {e}")
        return jsonify({'error': 'Failed to submit request'}), 500