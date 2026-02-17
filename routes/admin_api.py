
from flask import Blueprint, request, jsonify, session
from database import db
from models import Site, Admin, ClientConfig, Intent, Plan, BrandingSettings, PlatformSetting, SectorTemplate
from models.platform_settings import AuditLog
from flask import Blueprint, request, jsonify, session, current_app
from database import db
from models import Site, Admin, ClientConfig, Intent, ChatLog, Plan, PlatformSetting, SectorTemplate, TemplateFile, SiteFile
from services.importer import import_sector_template as importer_service
from services.file_service import save_template_file, delete_file_from_disk, provision_files_for_site
from functools import wraps
import traceback
import json
import os
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from models import Site, Admin, ClientConfig, Intent, Plan, BrandingSettings, PlatformSetting
from models.file_manager import SiteFile
from services.importer import import_sector_template as importer_service
from functools import wraps
import traceback
import json
from sqlalchemy.exc import IntegrityError # Import specific DB error
import os

# --- Super Admin Decorator (must be defined before use) ---
def super_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('admin_id')
        admin = Admin.query.get(user_id)
        if not admin or not getattr(admin, 'is_super', False):
            return jsonify({'error': 'Super Admin rights required'}), 403
        return func(*args, **kwargs)
    return wrapper

admin_api = Blueprint('admin_api', __name__)

## --- Audit Log: Paginated List ---
@admin_api.route('/super/audit-logs', methods=['GET'])
@super_admin_required
def get_audit_logs():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'logs': [
            {
                'id': log.id,
                'admin_id': log.admin_id,
                'site_id': log.site_id,
                'action': log.action,
                'timestamp': log.timestamp.isoformat()
            } for log in logs.items
        ],
        'total': logs.total,
        'page': logs.page,
        'pages': logs.pages
    })

## --- Health Check: DB File Accessibility ---
@admin_api.route('/super/health-check', methods=['GET'])
@super_admin_required
def health_check():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'chatbot.db')
    db_status = {'exists': False, 'writable': False}
    try:
        db_status['exists'] = os.path.isfile(db_path)
        if db_status['exists']:
            with open(db_path, 'a'):
                pass
            db_status['writable'] = True
    except Exception:
        db_status['writable'] = False
    return jsonify({'database': db_status})


# List all intent template files for super admin dashboard
@admin_api.route('/super/template_files', methods=['GET'])
@super_admin_required
def list_all_template_files():
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, 'intent_templates')
        files = [f for f in os.listdir(template_dir) if f.endswith('.json')]
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e), 'files': []}), 500

# Consultation Price API
@admin_api.route('/api/consultation-price', methods=['GET', 'POST'])
def consultation_price():
    site_id = request.args.get('site_id', type=int)
    if request.method == 'GET':
        cfg = ClientConfig.query.filter_by(client_id=site_id, key='consultation_price').first()
        return jsonify({'consultation_price': cfg.value if cfg else ''})
    else:
        price = request.json.get('consultation_price')
        cfg = ClientConfig.query.filter_by(client_id=site_id, key='consultation_price').first()
        if cfg:
            cfg.value = price
        else:
            cfg = ClientConfig(client_id=site_id, key='consultation_price', value=price)
            db.session.add(cfg)
        db.session.commit()
        return jsonify({'success': True, 'consultation_price': price})

def super_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get('admin_id')
        if not user_id: return jsonify({'error': 'Authentication required'}), 401
        admin = db.session.get(Admin, user_id)
        if not admin or not getattr(admin, 'is_super', False):
            return jsonify({'error': 'Super Admin rights required'}), 403
        return func(*args, **kwargs)
    return wrapper

# --- HEALTH CHECK ---
@admin_api.route('/ping', methods=['GET'])
def api_ping():
    return jsonify({'status': 'ok', 'message': 'Admin API is reachable'})

# --- CLIENT ROUTES (Legacy/Regular Admin) ---
@admin_api.route('/client/config', methods=['GET'])
def get_client_config():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    if not site_id: return jsonify({'error': 'No site linked'}), 400
    # Return all ClientConfig key-value pairs for this site
    configs = {c.key: c.value for c in ClientConfig.query.filter_by(client_id=site_id).all()}
    return jsonify({'config': configs})

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

@admin_api.route('/client/intents', methods=['GET'])
def get_client_intents():
    if 'admin_id' not in session: return jsonify({'error': 'Unauthorized'}), 401
    site_id = session.get('site_id')
    print(f"[DEBUG] Fetching intents for site_id={site_id}")
    intents = Intent.query.filter_by(site_id=site_id).all()
    print(f"[DEBUG] Found {len(intents)} intents for site_id={site_id}")
    return jsonify({'intents': [i.to_dict() for i in intents]})

# --- SUPER ADMIN: DASHBOARD STATS ---

@admin_api.route('/super/stats', methods=['GET'])
@super_admin_required
def get_super_stats():
    try:
        total_sites = Site.query.count()
        total_chats = db.session.query(func.coalesce(func.sum(ChatLog.id), 0)).scalar() or 0
        total_messages = db.session.query(func.coalesce(func.sum(Site.message_count), 0)).scalar() or 0
        
        recent_logs = db.session.query(ChatLog, Site.name).outerjoin(Site, ChatLog.site_id == Site.id)\
            .order_by(ChatLog.created_at.desc()).limit(5).all()
        
        activity_data = []
        for log, site_name in recent_logs:
            activity_data.append({
                'site_name': site_name or 'Unknown',
                'message': log.user_message[:50] + '...' if log.user_message else '',
                'intent': log.detected_intent or 'Unknown',
                'time': log.created_at.strftime('%H:%M') if log.created_at else ''
            })

        return jsonify({
            'total_sites': total_sites,
            'total_chats': int(total_messages),
            'recent_activity': activity_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# --- SUPER ADMIN: SITE MANAGEMENT ---

@admin_api.route('/super/sites', methods=['GET', 'POST'])
@super_admin_required
def manage_sites():
    if request.method == 'GET':
        try:
            sites = Site.query.all()
            return jsonify({'sites': [s.to_dict() for s in sites]})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.json or {}
            name = (data.get('name') or '').strip()
            domain = (data.get('domain') or '').strip() or None
            owner_email = (data.get('owner_email') or '').strip() or None
            status = (data.get('status') or 'active').strip()
            plan_id = data.get('plan_id')
            admin_username = (data.get('admin_username') or '').strip()
            admin_password = (data.get('admin_password') or '').strip()

            if not name:
                return jsonify({'error': 'Company Name is required'}), 400
            if not admin_username:
                return jsonify({'error': 'Admin username is required'}), 400
            if not admin_password:
                return jsonify({'error': 'Admin password is required'}), 400

            if Admin.query.filter_by(username=admin_username).first():
                return jsonify({'error': 'Admin username is already taken.'}), 400

            if domain and Site.query.filter_by(domain=domain).first():
                return jsonify({'error': 'Domain is already registered.'}), 400

            new_site = Site(
                name=name, domain=domain, owner_email=owner_email,
                status=status, plan_id=plan_id, bot_name=f"{name} Bot"
            )
            db.session.add(new_site)
            db.session.flush()

            new_admin = Admin(username=admin_username, site_id=new_site.id, is_super=False)
            new_admin.set_password(admin_password)
            db.session.add(new_admin)

            db.session.commit()
            return jsonify({'success': True, 'site': new_site.to_dict(), 'admin_user': admin_username})

        except IntegrityError:
            db.session.rollback()
            return jsonify({'error': 'Database integrity error'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites/<int:site_id>', methods=['PUT'])
@super_admin_required
def update_site_route(site_id):
    try:
        site = db.session.get(Site, site_id)
        if not site:
            return jsonify({'error': 'Site not found'}), 404
        
        data = request.json
        if 'name' in data: site.name = data['name']
        if 'domain' in data: site.domain = data['domain']
        if 'owner_email' in data: site.owner_email = data['owner_email']
        if 'status' in data: site.status = data['status']
        if 'plan_id' in data: site.plan_id = data['plan_id'] or None
        if 'client_requirements' in data and hasattr(site, 'client_requirements'):
             site.client_requirements = data['client_requirements']

        db.session.commit()
        return jsonify({'success': True, 'site': site.to_dict()})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Domain conflict or invalid data'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/sites/<int:site_id>/status', methods=['PUT'])
@super_admin_required
def toggle_site_status(site_id):
    try:
        site = db.session.get(Site, site_id)
        if not site: return jsonify({'error': 'Site not found'}), 404
        
        current_status = site.status or 'active'
        site.status = 'suspended' if current_status == 'active' else 'active'
            
        db.session.commit()
        return jsonify({'success': True, 'status': site.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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
    site = db.session.get(Site, site_id)
    if not site: return jsonify({'error': 'Site not found'}), 404
    data = request.json
    site.plan_id = data.get('plan_id')
    db.session.commit()
    return jsonify({'success': True})

@admin_api.route('/super/sites/<int:site_id>/template_data', methods=['GET'])
@super_admin_required
def get_site_template_data(site_id):
    try:
        site = db.session.get(Site, site_id)
        if not site:
            return jsonify({'error': 'Site not found'}), 404
        configs = ClientConfig.query.filter_by(client_id=site_id).all()
        config_dict = {c.key: c.value for c in configs}
        intents = Intent.query.filter_by(site_id=site_id).all()
        intent_list = [
            {
                'id': i.id,
                'intent_name': i.intent_name,
                'response': i.response[:50] + '...' if len(i.response) > 50 else i.response
            }
            for i in intents
        ]
        return jsonify({
            'site': site.to_dict() if hasattr(site, 'to_dict') else {'id': site.id, 'name': getattr(site, 'name', None)},
            'configs': config_dict,
            'intents': intent_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- FILE MANAGEMENT ROUTES ---

@admin_api.route('/sites/<int:site_id>/files', methods=['GET'])
@admin_api.route('/super/sites/<int:site_id>/files', methods=['GET'])
@super_admin_required
def list_site_files(site_id):
    """
    Fetch all files associated with a specific tenant (Site).
    Returns a JSON array of file objects.
    """
    try:
        files = SiteFile.query.filter_by(site_id=site_id).all()
        return jsonify({
            'files': [
                {
                    'id': f.id, 
                    'filename': f.filename, 
                    'file_type': f.file_type or 'unknown', 
                    'created_at': f.created_at.isoformat() if f.created_at else None
                } 
                for f in files
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_api.route('/sites/files/<int:file_id>', methods=['DELETE'])
@admin_api.route('/super/sites/<int:site_id>/files/<int:file_id>', methods=['DELETE'])
@super_admin_required
def delete_site_file(file_id, site_id=None):
    file_record = db.session.get(SiteFile, file_id)
    if not file_record: return jsonify({'error': 'File not found'}), 404
    if site_id and file_record.site_id != site_id: return jsonify({'error': 'Unauthorized'}), 403
    delete_file_from_disk(file_record.file_path)
    db.session.delete(file_record)
    db.session.commit()
    return jsonify({'success': True})

# --- TEMPLATE ROUTES ---

@admin_api.route('/super/templates', methods=['GET', 'POST'])
@super_admin_required
def manage_templates():
    if request.method == 'GET':
        templates = SectorTemplate.query.all()
        return jsonify({'templates': [t.to_dict() for t in templates]})
    elif request.method == 'POST':
        try:
            data = request.json
            content = data.get('content') 
            if isinstance(content, dict): content = json.dumps(content)
            template = SectorTemplate(name=data.get('name'), description=data.get('description'), structure_json=content)
            db.session.add(template)
            db.session.commit()
            return jsonify({'success': True, 'template': template.to_dict()})
        except Exception as e: return jsonify({'error': str(e)}), 500

@admin_api.route('/super/templates/<int:template_id>/upload', methods=['POST'])
@super_admin_required
def upload_template_files_route(template_id):
    if 'files' not in request.files: return jsonify({'error': 'No files'}), 400
    files = request.files.getlist('files')
    count = 0
    for file in files:
        if file.filename == '': continue
        path, filename, ext = save_template_file(file, template_id)
        if path:
            db.session.add(TemplateFile(template_id=template_id, filename=filename, file_path=path, file_type=ext))
            count += 1
    if count > 0: db.session.commit()
    return jsonify({'success': True, 'count': count})

@admin_api.route('/super/templates/<int:template_id>/files', methods=['GET'])
@super_admin_required
def list_template_files(template_id):
    files = TemplateFile.query.filter_by(template_id=template_id).all()
    return jsonify({'files': [f.to_dict() for f in files]})

@admin_api.route('/super/templates/files/<int:file_id>', methods=['DELETE'])
@super_admin_required
def delete_template_file(file_id):
    f = db.session.get(TemplateFile, file_id)
    if f:
        delete_file_from_disk(f.file_path)
        db.session.delete(f)
        db.session.commit()
    return jsonify({'success': True})

@admin_api.route('/super/sites/<int:site_id>/apply_template', methods=['POST'])
@super_admin_required
def apply_sector_template_route(site_id):
    """
    Applies a template to a site.
    1. Copies Intents & Settings (logic from importer).
    2. COPIES FILES from TemplateFile -> SiteFile.
    """
    try:
        data = request.json
        template = db.session.get(SectorTemplate, data.get('template_id'))
        if not template: return jsonify({'error': 'Template not found'}), 404
        
        # 1. Apply Logic
        import json
        res = importer_service(site_id, json.loads(template.structure_json))
        if not res['success']: return jsonify(res)
        
        # 2. Copy Files Logic (Crucial Fix)
        t_files = TemplateFile.query.filter_by(template_id=template.id).all()
        files_copied = 0
        
        if t_files:
            # Helper to copy physical files and return data for DB
            new_files_data = provision_files_for_site(site_id, t_files)
            
            for file_data in new_files_data:
                # Check if file already exists for this site to avoid duplicates
                existing = SiteFile.query.filter_by(site_id=site_id, filename=file_data['filename']).first()
                if not existing:
                    new_site_file = SiteFile(
                        site_id=site_id,
                        filename=file_data['filename'],
                        file_path=file_data['file_path'],
                        file_type=file_data['file_type']
                    )
                    db.session.add(new_site_file)
                    files_copied += 1
            
            db.session.commit()
            
        res['files_provisioned'] = files_copied
        return jsonify(res)
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/import_template', methods=['POST'])
@super_admin_required
def upload_template_route():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    try:
        json_data = json.load(request.files['file'])
        res = importer_service(int(request.form.get('site_id')), json_data)
        return jsonify(res)
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- PLAN MANAGEMENT ROUTES ---

@admin_api.route('/super/plans', methods=['GET', 'POST'])
@super_admin_required
def manage_plans():
    if request.method == 'GET':
        try:
            plans = Plan.query.all()
            return jsonify({'plans': [p.to_dict() for p in plans]})
        except Exception as e: return jsonify({'error': str(e)}), 500
    elif request.method == 'POST':
        try:
            data = request.json
            new_plan = Plan(name=data.get('name'), price=float(data.get('price', 0)), max_intents=int(data.get('max_intents', 0)), max_monthly_chats=int(data.get('max_monthly_chats', 0)), is_active=True)
            db.session.add(new_plan)
            db.session.commit()
            return jsonify({'success': True, 'plan': new_plan.to_dict()})
        except IntegrityError: db.session.rollback(); return jsonify({'error': 'Plan name exists'}), 400
        except Exception as e: db.session.rollback(); return jsonify({'error': str(e)}), 500

@admin_api.route('/super/plans/<int:plan_id>', methods=['PUT', 'DELETE'])
@super_admin_required
def update_or_delete_plan(plan_id):
    plan = Plan.query.get(plan_id)
    if not plan: return jsonify({'error': 'Plan not found'}), 404
    if request.method == 'PUT':
        try:
            data = request.json
            if 'name' in data: plan.name = data['name']
            if 'price' in data: plan.price = float(data['price'])
            if 'max_intents' in data: plan.max_intents = int(data['max_intents'])
            if 'max_monthly_chats' in data: plan.max_monthly_chats = int(data['max_monthly_chats'])
            db.session.commit()
            return jsonify({'success': True, 'plan': plan.to_dict()})
        except Exception as e: return jsonify({'error': str(e)}), 500
    elif request.method == 'DELETE':
        try:
            if Site.query.filter_by(plan_id=plan_id).count() > 0: return jsonify({'error': 'Plan in use'}), 400
            db.session.delete(plan)
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e: return jsonify({'error': str(e)}), 500

@admin_api.route('/super/settings', methods=['GET', 'POST'])
@super_admin_required
def manage_platform_settings():
    if request.method == 'GET':
        settings = PlatformSetting.query.all()
        return jsonify({'settings': [s.to_dict() for s in settings]})
    elif request.method == 'POST':
        try:
            data = request.json
            setting = db.session.get(PlatformSetting, data.get('key'))
            if setting:
                setting.value = data.get('value')
                if data.get('description'): setting.description = data.get('description')
            else:
                setting = PlatformSetting(key=data.get('key'), value=data.get('value'), description=data.get('description'))
                db.session.add(setting)
            db.session.commit()
            return jsonify({'success': True, 'setting': setting.to_dict()})
        except Exception as e: return jsonify({'error': str(e)}), 500
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

@admin_api.route('/super/sites', methods=['GET'])
@super_admin_required
def list_sites():
    try:
        sites = Site.query.all()
        return jsonify({'sites': [s.to_dict() for s in sites]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_api.route('/super/stats', methods=['GET'])
@super_admin_required
def super_stats():
    try:
        site_count = Site.query.count()
        admin_count = Admin.query.count()
        plan_count = Plan.query.count()
        # Sum all message_count fields for total chats
        total_chats = db.session.query(db.func.sum(Site.message_count)).scalar() or 0
        return jsonify({
            'site_count': site_count,
            'admin_count': admin_count,
            'plan_count': plan_count,
            'total_chats': total_chats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
