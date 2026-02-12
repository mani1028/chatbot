from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS  # Enable CORS for cross-origin requests
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
CORS(app)  # Allow all domains to access the API
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

db.init_app(app)

# --- HELPER FUNCTIONS ---
def login_required(f):
    """
    Decorator to require admin login for routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- INITIALIZATION ---
with app.app_context():
    init_db(app)
    
    # 1. Auto-Create Super Admin if not exists
    super_admin = Admin.query.filter_by(username=ADMIN_USERNAME).first()
    if not super_admin:
        print(f"Creating Super Admin: {ADMIN_USERNAME}")
        super_admin = Admin(username=ADMIN_USERNAME, is_super=True)
        super_admin.set_password(ADMIN_PASSWORD)
        db.session.add(super_admin)
        db.session.commit()

    # 2. Auto-Create Default Site (ID: 1)
    default_site = Site.query.get(1)
    if not default_site:
        print("Creating Default Site (ID: 1)...")
        default_site = Site(
            name="Platform Demo",
            domain="localhost",
            bot_name="Demo Bot"
        )
        db.session.add(default_site)
        db.session.commit()
        
        # Link Super Admin to this site
        if super_admin:
            super_admin.site_id = 1
            db.session.commit()

    # 3. Default Branding
    if BrandingSettings.query.count() == 0:
        from config import DEFAULT_BRANDING
        branding = BrandingSettings(**DEFAULT_BRANDING)
        db.session.add(branding)
        db.session.commit()

# Register Blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(admin_api, url_prefix='/admin/api')

# --- PUBLIC ROUTES ---

@app.route('/')
def index():
    """
    Main Landing Page for the SaaS Platform
    """
    return render_template('landing.html')
@app.route('/widget.js')
def widget_embed():
    from flask import send_file
    # UPDATED: Pointing to the file you chose (chatbot/static/widget.js)
    return send_file('static/widget.js', mimetype='application/javascript')

@app.route('/api/widget-settings')
def get_widget_settings():
    branding = BrandingSettings.query.first()
    if not branding:
        return jsonify({})
    response = jsonify(branding.to_dict())
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
    admin = Admin.query.get(user_id)
    if not admin or not getattr(admin, 'is_super', False):
        return "Access Denied: Super Admin rights required", 403
    return render_template('super_dashboard.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template('admin_dashboard.html', site_id=session.get('site_id'))

@app.route('/admin/api/client/intents', methods=['GET'])
@login_required
def get_client_intents():
    site_id = session.get('site_id')
    if not site_id:
        return jsonify({'error': 'No site linked to this admin'}), 400
    intents = Intent.query.filter_by(site_id=site_id).all()
    return jsonify({'intents': [i.to_dict() for i in intents]})

# --- ERROR HANDLERS ---

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