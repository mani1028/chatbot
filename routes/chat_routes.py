from flask import Blueprint, request, jsonify
from models.site import Site
from models.usage import Usage
from models.plan import Plan, Subscription
from services.chat_service import process_message
from database import db, limiter
from datetime import datetime
from models import LeadCapture
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
    lead = LeadCapture(
        site_id=site.id,
        user_name=name,
        user_email=email,
        user_phone=phone,
        session_id=session_id,
        question_context=user_message
    )
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
    if usage and usage.messages >= usage_limit:
        if site.status != 'suspended':
            site.status = 'suspended'
            db.session.commit()
        return jsonify({'error': 'Usage limit exceeded. Site suspended.'}), 403

    if not site.is_active:
        return jsonify({'error': 'This site is currently suspended.'}), 403

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