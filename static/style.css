from flask import Blueprint, request, jsonify, session
from database import db
from models import Site, Admin, ClientConfig, Intent, ChatLog, Plan, PlatformSetting, SectorTemplate
from models.file_manager import SiteFile
from services.importer import import_sector_template as importer_service
from services.file_service import delete_file_from_disk
from functools import wraps
import traceback
import json
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
        return jsonify({'error': str(e)}), 500

@admin_api.route('/client/stats', methods=['GET'])
def get_client_stats():
    """Fetch the real status of the client's bot"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    site = Site.query.get(site_id)
    if not site:
        return jsonify({'error': 'Site not found'}), 404

    return jsonify({
        'status': site.status,
        'bot_name': site.bot_name,
        'plan_name': site.plan.name if getattr(site, 'plan', None) else 'Unknown Plan'
    })

@admin_api.route('/client/intents', methods=['GET'])
def get_client_intents():
    """Fetch assigned intents for this specific client"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    intents = Intent.query.filter_by(site_id=site_id).all()
    intent_list = [
        {
            'id': i.id,
            'intent_name': getattr(i, 'intent_name', ''),
            'response': getattr(i, 'response', '')
        }
        for i in intents
    ]
    return jsonify({'intents': intent_list})

@admin_api.route('/client/intents', methods=['POST'])
def add_client_intent():
    """Add a new intent"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    try:
        data = request.json
        new_intent = Intent(
            site_id=site_id,
            intent_name=data.get('intent_name'),
            response=data.get('response')
        )
        db.session.add(new_intent)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_api.route('/client/intents/<int:intent_id>', methods=['PUT'])
def update_client_intent(intent_id):
    """Update an existing assigned intent"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    try:
        intent = Intent.query.filter_by(id=intent_id, site_id=site_id).first()
        if not intent:
            return jsonify({'error': 'Intent not found'}), 404

        data = request.json
        intent.intent_name = data.get('intent_name', intent.intent_name)
        intent.response = data.get('response', intent.response)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_api.route('/client/intents/<int:intent_id>', methods=['DELETE'])
def delete_client_intent(intent_id):
    """Delete an assigned intent"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    try:
        intent = Intent.query.filter_by(id=intent_id, site_id=site_id).first()
        if not intent:
            return jsonify({'error': 'Intent not found'}), 404

        db.session.delete(intent)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- SUPER ADMIN: DASHBOARD STATS ---
@admin_api.route('/super/stats', methods=['GET'])
@super_admin_required
def get_super_stats():
    try:
        total_sites = Site.query.count()
        total_chats = ChatLog.query.count()
        recent_logs = db.session.query(ChatLog, Site.name).join(Site, ChatLog.site_id == Site.id)\
            .order_by(ChatLog.created_at.desc()).limit(5).all()
        
        activity_data = []
        for log, site_name in recent_logs:
            activity_data.append({
                'site_name': site_name,
                'message': log.user_message[:50] + '...',
                'intent': log.detected_intent,
                'time': log.created_at.strftime('%H:%M')
            })

        return jsonify({
            'total_sites': total_sites,
            'total_chats': total_chats,
            'recent_activity': activity_data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- SUPER ADMIN: SITE MANAGEMENT ---
@admin_api.route('/super/sites', methods=['GET'])
@super_admin_required
def list_sites_route():
    sites = Site.query.all()
    return jsonify({'sites': [s.to_dict() for s in sites]})

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
            return jsonify({'error': f'Username "{admin_user}" taken.'}), 400

        default_plan = Plan.query.filter_by(name="Starter").first()
        plan_id = default_plan.id if default_plan else None

        site = Site(
            name=name, domain=domain, bot_name=data.get('bot_name', 'ChatBot'),
            plan_id=plan_id, status='active', owner_email=data.get('owner_email')
        )
        db.session.add(site)
        db.session.flush()

        new_admin = Admin(username=admin_user, site_id=site.id, is_super=False)
        new_admin.set_password(admin_pass)
        db.session.add(new_admin)

        db.session.commit()
        return jsonify({'success': True, 'site': site.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites/<int:site_id>/status', methods=['PUT'])
@super_admin_required
def toggle_site_status(site_id):
    site = Site.query.get(site_id)
    if not site: return jsonify({'error': 'Site not found'}), 404
    
    site.status = 'suspended' if site.status == 'active' else 'active'
    site.is_active = (site.status == 'active')
    
    db.session.commit()
    return jsonify({'success': True, 'status': site.status})

@admin_api.route('/super/sites/<int:site_id>/impersonate', methods=['POST'])
@super_admin_required
def impersonate_site(site_id):
    admin = Admin.query.filter_by(site_id=site_id, is_super=False).first()
    if not admin: return jsonify({'error': 'No admin user found'}), 404
    session['admin_id'] = admin.id
    session['site_id'] = site_id
    return jsonify({'success': True, 'redirect': '/admin/dashboard'})

@admin_api.route('/super/sites/<int:site_id>/plan', methods=['PUT'])
@super_admin_required
def update_site_plan(site_id):
    site = Site.query.get(site_id)
    if not site: return jsonify({'error': 'Site not found'}), 404
    data = request.json
    site.plan_id = data.get('plan_id')
    db.session.commit()
    return jsonify({'success': True})

@admin_api.route('/super/sites/<int:site_id>/template_data', methods=['GET'])
@super_admin_required
def get_site_template_data(site_id):
    """Fetch the configuration and intents applied to a specific tenant"""
    try:
        site = Site.query.get(site_id)
        if not site:
            return jsonify({'error': 'Site not found'}), 404

        configs = ClientConfig.query.filter_by(client_id=site_id).all()
        config_dict = {c.key: c.value for c in configs}

        intents = Intent.query.filter_by(site_id=site_id).all()
        intent_list = [
            {
                'id': i.id,
                'name': i.intent_name,  # Fixed: i.name -> i.intent_name
                'response': i.response[:50] + '...' if len(i.response) > 50 else i.response
            }
            for i in intents
        ]

        return jsonify({
            'success': True,
            'config': config_dict,
            'intent_count': len(intents),
            'intents': intent_list
        })
    except Exception as e:
        print("Template Data Fetch Error:", e)
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites/<int:site_id>/files', methods=['GET'])
@super_admin_required
def list_site_files(site_id):
    site = Site.query.get(site_id)
    if not site:
        return jsonify({'error': 'Site not found'}), 404

    files = SiteFile.query.filter_by(site_id=site_id).order_by(SiteFile.created_at.desc()).all()
    return jsonify({'success': True, 'files': [f.to_dict() for f in files]})

@admin_api.route('/super/sites/<int:site_id>/files/<int:file_id>', methods=['DELETE'])
@super_admin_required
def delete_site_file(site_id, file_id):
    site_file = SiteFile.query.filter_by(site_id=site_id, id=file_id).first()
    if not site_file:
        return jsonify({'error': 'File not found'}), 404

    disk_deleted = delete_file_from_disk(site_file.file_path)
    db.session.delete(site_file)
    db.session.commit()
    return jsonify({'success': True, 'deleted_id': file_id, 'disk_deleted': disk_deleted})

@admin_api.route('/super/plans', methods=['GET'])
@super_admin_required
def list_plans():
    plans = Plan.query.all()
    return jsonify({'plans': [p.to_dict() for p in plans]})

# --- SUPER ADMIN: SECTOR TEMPLATES ---

@admin_api.route('/super/templates', methods=['GET'])
@super_admin_required
def list_templates():
    templates = SectorTemplate.query.all()
    return jsonify({'templates': [t.to_dict() for t in templates]})

@admin_api.route('/super/templates', methods=['POST'])
@super_admin_required
def create_template():
    try:
        data = request.json
        name = data.get('name')
        description = data.get('description')
        content = data.get('content') 

        if isinstance(content, dict):
            content = json.dumps(content)

        template = SectorTemplate(name=name, description=description, structure_json=content)
        db.session.add(template)
        db.session.commit()
        return jsonify({'success': True, 'template': template.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites/<int:site_id>/apply_template', methods=['POST'])
@super_admin_required
def apply_sector_template_route(site_id):
    try:
        data = request.json
        template_id = data.get('template_id')
        
        template = SectorTemplate.query.get(template_id)
        if not template:
            return jsonify({'error': 'Template not found'}), 404

        import json
        template_data = json.loads(template.structure_json)
        result = importer_service(site_id, template_data)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- RESTORED ROUTE FOR FILE UPLOAD TEMPLATE IMPORT ---
@admin_api.route('/super/import_template', methods=['POST'])
@super_admin_required
def upload_template_route():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    site_id = request.form.get('site_id')
    
    try:
        # Load JSON from uploaded file
        json_data = json.load(file)
        # Call the importer service
        result = importer_service(int(site_id), json_data)
        
        if result['success']: return jsonify(result)
        return jsonify({'error': result['message']}), 500
    except Exception as e:
        print("Import Error:", e)
        return jsonify({'error': str(e)}), 500

# --- SUPER ADMIN: PLATFORM SETTINGS (KV) ---

@admin_api.route('/super/settings', methods=['GET'])
@super_admin_required
def get_platform_settings():
    settings = PlatformSetting.query.all()
    return jsonify({'settings': [s.to_dict() for s in settings]})

@admin_api.route('/super/settings', methods=['POST'])
@super_admin_required
def update_platform_setting():
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        description = data.get('description')

        setting = PlatformSetting.query.get(key)
        if setting:
            setting.value = value
            if description: setting.description = description
        else:
            setting = PlatformSetting(key=key, value=value, description=description)
            db.session.add(setting)
        
        db.session.commit()
        return jsonify({'success': True, 'setting': setting.to_dict()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500