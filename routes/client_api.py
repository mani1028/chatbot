from flask import Blueprint, jsonify, request, session
from models.lead_capture import LeadCapture
from models.site import Site
from database import db

client_api = Blueprint('client_api', __name__, url_prefix='/api/client')

@client_api.route('/leads', methods=['GET'])
def view_leads():
    site_id = session.get('site_id')
    if not site_id:
        return jsonify({"error": "Unauthorized"}), 403

    leads = LeadCapture.query.filter_by(site_id=site_id).all()
    return jsonify({"leads": [lead.to_dict() for lead in leads]})

# Add other client-specific routes here