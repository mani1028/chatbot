from flask import Blueprint, request, jsonify, session
from database import db
from models import Site, Admin, ClientConfig, Intent, BrandingSettings
from services.importer import import_sector_template
from functools import wraps
import traceback
from sqlalchemy.exc import IntegrityError

admin_api = Blueprint('admin_api', __name__)

def super_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('admin_id')
        admin = Admin.query.get(user_id)
        if not admin or not getattr(admin, 'is_super', False):
            return jsonify({'error': 'Super Admin rights required'}), 403
        return func(*args, **kwargs)
    return wrapper

# --- CLIENT ROUTES ---

@admin_api.route('/client/config', methods=['GET'])
def get_client_config():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    if not site_id: return jsonify({'error': 'No site linked'}), 400
    
    configs = ClientConfig.query.filter_by(client_id=site_id).all()
    return jsonify({'config': {c.key: c.value for c in configs}})

@admin_api.route('/client/config', methods=['POST'])
def update_client_config():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    
    try:
        data = request.json
        for key, value in data.items():
            conf = ClientConfig.query.filter_by(client_id=site_id, key=key).first()
            if conf:
                conf.value = value
            else:
                db.session.add(ClientConfig(client_id=site_id, key=key, value=value))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        print("Config Update Error:", e)
        return jsonify({'error': str(e)}), 500

@admin_api.route('/client/intents', methods=['GET'])
def get_client_intents():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    intents = Intent.query.filter_by(site_id=site_id).all()
    return jsonify({'intents': [i.to_dict() for i in intents]})

# --- BRANDING ROUTES (NEW) ---

@admin_api.route('/client/branding', methods=['GET'])
def get_branding():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()
    
    # Create default if missing for this tenant
    if not branding:
        branding = BrandingSettings(site_id=site_id)
        db.session.add(branding)
        db.session.commit()
        
    return jsonify({'branding': branding.to_dict()})

@admin_api.route('/client/branding', methods=['POST'])
def update_branding():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    
    try:
        data = request.json
        branding = BrandingSettings.query.filter_by(site_id=site_id).first()
        if not branding:
            branding = BrandingSettings(site_id=site_id)
            db.session.add(branding)
            
        # Update fields
        if 'bot_name' in data: branding.bot_name = data['bot_name']
        if 'initial_message' in data: branding.initial_message = data['initial_message']
        if 'primary_color' in data: branding.primary_color = data['primary_color']
        if 'logo_url' in data: branding.logo_url = data['logo_url']
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- SUPER ADMIN ROUTES ---

@admin_api.route('/super/sites', methods=['POST'])
@super_admin_required
def create_site_route():
    try:
        data = request.json
        name = data.get('name')
        admin_user = data.get('admin_username')
        admin_pass = data.get('admin_password')
        domain = data.get('domain') or None 

        if not name or not admin_user or not admin_pass:
            return jsonify({'error': 'Missing fields'}), 400

        if Admin.query.filter_by(username=admin_user).first():
            return jsonify({'error': f'Username "{admin_user}" is already taken.'}), 400

        # 1. Create Site
        site = Site(
            name=name,
            domain=domain,
            bot_name=data.get('bot_name', 'ChatBot')
        )
        db.session.add(site)
        db.session.flush() 

        # 2. Create Admin
        new_admin = Admin(username=admin_user, site_id=site.id, is_super=False)
        new_admin.set_password(admin_pass)
        db.session.add(new_admin)
        
        # 3. Create Default Branding
        default_branding = BrandingSettings(site_id=site.id, bot_name=site.bot_name)
        db.session.add(default_branding)

        db.session.commit()
        return jsonify({'success': True, 'site': site.to_dict()})

    except IntegrityError as e:
        db.session.rollback()
        if 'UNIQUE constraint failed: sites.domain' in str(e):
            return jsonify({'error': f'The domain "{domain}" is already used.'}), 400
        return jsonify({'error': 'Database error: Duplicate data.'}), 400

    except Exception as e:
        db.session.rollback()
        print("Create Site Error:")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites', methods=['GET'])
@super_admin_required
def list_sites_route():
    sites = Site.query.all()
    return jsonify({'sites': [s.to_dict() for s in sites]})

@admin_api.route('/super/import_template', methods=['POST'])
@super_admin_required
def upload_template_route():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    site_id = request.form.get('site_id')
    
    try:
        import json
        json_data = json.load(file)
        result = import_sector_template(int(site_id), json_data)
        if result['success']: return jsonify(result)
        return jsonify({'error': result['message']}), 500
    except Exception as e:
        print("Import Error:", e)
        return jsonify({'error': str(e)}), 500