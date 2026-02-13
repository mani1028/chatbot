from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
from functools import wraps
import os
import json

from config import (
    SECRET_KEY, DEBUG, SQLALCHEMY_DATABASE_URI, 
    SQLALCHEMY_TRACK_MODIFICATIONS, ADMIN_USERNAME, ADMIN_PASSWORD
)
from database import db, init_db
from models import Admin, BrandingSettings, Site, ClientConfig
from routes.chat_routes import chat_bp
from routes.admin_api import admin_api
from services.chat_service import process_message

app = Flask(__name__)
CORS(app) 
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

# --- 1. INITIALIZE SOCKETIO (REAL-TIME ENGINE) ---
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

db.init_app(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- INITIALIZATION LOGIC ---
with app.app_context():
    init_db(app)
    # Ensure default admins exist (logic preserved from original)
    try:
        if not Admin.query.filter_by(username=ADMIN_USERNAME).first():
            print(f"Creating default super admin: {ADMIN_USERNAME}")
            admin = Admin(username=ADMIN_USERNAME, is_super=True)
            admin.set_password(ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
            
        if not Admin.query.filter_by(username='client').first():
            site = Site.query.get(1)
            if not site:
                site = Site(name="Demo Company", domain="localhost")
                db.session.add(site)
                db.session.flush()
            client_admin = Admin(username='client', site_id=site.id, is_super=False)
            client_admin.set_password('client123')
            db.session.add(client_admin)
            db.session.commit()
    except Exception as e:
        print(f"Error creating default users: {e}")

app.register_blueprint(chat_bp)
app.register_blueprint(admin_api, url_prefix='/admin/api')

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/widget.js')
def widget_embed():
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
    api_url = request.args.get('api', 'http://localhost:5000')
    site_id = request.args.get('site_id', 1, type=int)
    
    # FIX: Fetch branding data so the template doesn't crash
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()
    
    # Fallback if no branding exists yet
    if not branding:
        branding = BrandingSettings(site_id=site_id)
        # We don't commit here, just creating a transient object for display
    
    return render_template('widget.html', api_url=api_url, branding=branding)

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

@app.route('/super/dashboard')
@login_required
def super_dashboard():
    return render_template('super_dashboard.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    return render_template('admin_dashboard.html', site_id=session.get('site_id'))

# --- 2. WEBSOCKET EVENTS (SAAS LOGIC) ---

@socketio.on('join')
def on_join(data):
    """User joins a specific site room"""
    site_id = data.get('site_id')
    room = f"site_{site_id}"
    join_room(room)
    print(f"User joined room: {room}")

@socketio.on('client_message')
def handle_client_message(data):
    """
    Handle real-time message from widget.
    Data expected: { 'message': '...', 'site_id': 1, 'session_id': '...' }
    """
    site_id = data.get('site_id')
    user_msg = data.get('message')
    session_id = data.get('session_id')
    
    # 1. Check AI Mode
    ai_config = ClientConfig.query.filter_by(client_id=site_id, key='ai_mode').first()
    ai_enabled = ai_config.value == 'on' if ai_config else False

    # 2. Emit typing indicator to the specific user (or room)
    # In a real socket scenario, we usually emit back to the specific client `request.sid`
    emit('typing', {'status': 'active'})

    # 3. Process Logic (Simulating AI Delay for UX)
    import time
    
    # Check if we should use the Intent Engine or Mock OpenAI
    # (Here we use the existing robust intent engine, but wrap it for sockets)
    response_obj = process_message(site_id, user_msg, session_id)
    
    # Simulate thinking time based on message length
    time.sleep(1.0) 

    # 4. Send Response
    emit('bot_response', {
        'reply': response_obj.reply,
        'intent': response_obj.intent_name,
        'confidence': response_obj.confidence
    })

if __name__ == '__main__':
    # USE SOCKETIO.RUN INSTEAD OF APP.RUN
    socketio.run(app, port=5000, debug=DEBUG)