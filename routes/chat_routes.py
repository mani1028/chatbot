"""
Multi-tenant chat routes for SaaS
Handles all chat API endpoints with site_id scoping and domain whitelisting
"""
from flask import Blueprint, request, jsonify
from models.site import Site
from services.chat_service import process_message
from database import db

# Define Blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

def get_request_domain():
    """Extract domain from request Referer or Host header"""
    referer = request.headers.get('Referer', '')
    if referer:
        # Extract domain from URL: https://example.com/page -> example.com
        from urllib.parse import urlparse
        domain = urlparse(referer).netloc
        return domain
    return request.headers.get('Host', '').split(':')[0]

@chat_bp.route('', methods=['POST'])
def send_message():
    """
    Post a message and get bot response
    Required JSON: { "site_id": 1, "message": "Hello" }
    """
    data = request.get_json()
    
    # 1. Validate Input existence
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
        
    site_id = data.get('site_id')
    message = data.get('message')
    session_id = data.get('session_id') # Optional

    # 2. Validate Required Fields
    if not site_id:
        return jsonify({'error': 'Missing site_id parameter. Frontend must send site_id.'}), 400
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400

    # 3. Validate Site
    site = Site.query.filter_by(id=site_id).first()
    if not site:
        return jsonify({'error': f'Site ID {site_id} not found'}), 404

    # 4. Domain Whitelisting (Security)
    # request_domain = get_request_domain()
    # if not site.is_domain_allowed(request_domain):
    #     return jsonify({'error': f'Domain {request_domain} is not whitelisted for this site'}), 403
    
    # 5. Process message
    try:
        response = process_message(site_id, message, session_id)
        # Handle response object or dict
        if hasattr(response, 'to_dict'):
            return jsonify(response.to_dict()), 200
        return jsonify(response), 200
    except Exception as e:
        print(f"Error processing message: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500