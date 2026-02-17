from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import os
from datetime import datetime

# Import config and database
from config import (
    SECRET_KEY, DEBUG, SQLALCHEMY_DATABASE_URI, 
    SQLALCHEMY_TRACK_MODIFICATIONS, ADMIN_USERNAME, ADMIN_PASSWORD
)
from database import db, init_db
from models import Admin, BrandingSettings, Site, Intent, IntentPhrase, ChatLog
from routes.chat_routes import chat_bp
from routes.admin_api import admin_api

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

db.init_app(app)

# --- HELPER FUNCTIONS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- INITIALIZATION ---
with app.app_context():
    init_db(app)
    
    # 1. Auto-Create Super Admin
    super_admin = Admin.query.filter_by(username=ADMIN_USERNAME).first()
    if not super_admin:
        print(f"Creating Super Admin: {ADMIN_USERNAME}")
        super_admin = Admin(username=ADMIN_USERNAME, is_super=True)
        super_admin.set_password(ADMIN_PASSWORD)
        db.session.add(super_admin)
        db.session.commit()

    # 2. Auto-Create Plans (New Feature)
    try:
        if Plan.query.count() == 0:
            print("Seeding Default Plans...")
            plans = [
                Plan(name="Free Tier", max_monthly_chats=100, price=0.0),
                Plan(name="Starter", max_monthly_chats=1000, price=29.0),
                Plan(name="Pro", max_monthly_chats=10000, price=99.0),
                Plan(name="Enterprise", max_monthly_chats=100000, price=499.0)
            ]
            db.session.add_all(plans)
            db.session.commit()
    except Exception as e:
        print(f"Plan seeding skipped: {e}")

    # 3. Auto-Create Default Site
    try:
        default_site = db.session.get(Site, 1)
        if not default_site:
            print("Creating Default Site (ID: 1)...")
            # Assign 'Starter' plan by default
            starter_plan = Plan.query.filter_by(name="Starter").first()
            default_site = Site(
                name="Platform Demo",
                domain="localhost",
                bot_name="Demo Bot",
                plan_id=starter_plan.id if starter_plan else None
            )
            db.session.add(default_site)
            db.session.commit()
            
            # Link Super Admin to this site
            if super_admin:
                super_admin.site_id = 1
                db.session.commit()
    except Exception as e:
        print(f"Default site creation skipped: {e}")

    # 4. Default Branding
    if BrandingSettings.query.count() == 0:
        from config import DEFAULT_BRANDING
        branding = BrandingSettings(**DEFAULT_BRANDING)
        db.session.add(branding)
        db.session.commit()

# Register Blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(admin_api, url_prefix='/admin/api') # <--- THIS IS CORRECT

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/widget.js')
def widget_embed():
    from flask import send_file
    return send_file('static/widget.js', mimetype='application/javascript')

@app.route('/api/widget-settings')
def get_widget_settings():
    site_id = request.args.get('site_id', 1, type=int)
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()
    
    # Check AI Mode status
    ai_config = ClientConfig.query.filter_by(client_id=site_id, key='ai_mode').first()
    ai_enabled = ai_config.value == 'on' if ai_config else False

    if not branding:
        return jsonify({
            'bot_name': 'ChatBot',
            'primary_color': '#667eea',
            'initial_message': 'How can I help?',
            'theme_mode': 'light',
            'ai_enabled': ai_enabled
        })
        
    data = branding.to_dict()
    data['ai_enabled'] = ai_enabled
    response = jsonify(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/widget/init.html')
def widget_init():
    branding = BrandingSettings.query.first()
    api_url = request.args.get('api', 'http://localhost:5000')
    return render_template('widget.html', api_url=api_url, branding=branding)

# --- AUTHENTICATION ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session['site_id'] = getattr(admin, 'site_id', None)
            session.permanent = True
            
            if getattr(admin, 'is_super', False):
                return redirect(url_for('super_dashboard'))
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

# --- DASHBOARDS ---

@app.route('/super/dashboard')
@login_required
def super_dashboard():
    user_id = session.get('admin_id')
    admin = db.session.get(Admin, user_id)
    if not admin or not getattr(admin, 'is_super', False):
        return "Access Denied: Super Admin rights required", 403
    return render_template('super_dashboard.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template('admin_dashboard.html', site_id=session.get('site_id'))

# --- ERROR HANDLERS ---

@app.errorhandler(400)
def bad_request(error):
    print(f"400 Bad Request Error: {error}")
    return jsonify({'error': 'Bad Request', 'message': str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("=" * 50)
    print(f"--- AI Chatbot Server Running on http://localhost:5000 ---")
    print(f"Super Admin Login: http://localhost:5000/admin/login")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=DEBUG)