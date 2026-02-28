from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
from functools import wraps
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

# Config
from config import (
    SECRET_KEY,
    DEBUG,
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    WIDGET_EMBED_URL
)

# Shared Extensions
db = SQLAlchemy()
from database import db, limiter, init_db
from models import Admin, BrandingSettings, Site, ClientConfig

# Blueprints
from routes.chat_routes import chat_bp
from routes.admin_api import admin_api
from routes.super_admin_api import super_admin_api

def create_app():
    app = Flask(__name__)
    
    # Load Config
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['DEBUG'] = DEBUG
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

    # Initialize Extensions
    db.init_app(app)
    limiter.init_app(app)
    
    # CORS Setup
    CORS(app, origins="*")  # Allow all origins temporarily
    
    # Register Blueprints
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_api, url_prefix="/admin/api")
    app.register_blueprint(super_admin_api, url_prefix='/api/super')

    return app

app = create_app()

# SocketIO Setup
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# Initialize Database Tables
with app.app_context():
    init_db(app)
    if not Admin.query.first():
        site = Site(name="Default Site", domain="default.com", status="active", bot_name="Default Bot")
        db.session.add(site)
        db.session.flush()

        admin = Admin(username="admin", site_id=site.id, is_super=True)
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    return render_template("landing.html")

@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/widget.js")
def widget_embed():
    return send_file("static/widget.js", mimetype="application/javascript")

@app.route("/api/widget-settings")
def get_widget_settings():
    # FIX: Read 'site_key' instead of 'site_id'
    site_key = request.args.get("site_key")
    site = Site.query.filter_by(public_key=site_key).first()
    if not site:
        return jsonify({
            "bot_name": "ChatBot",
            "primary_color": "#667eea",
            "initial_message": "How can I help?",
            "theme_mode": "light",
            "ai_enabled": False
        })
    branding = BrandingSettings.query.filter_by(site_id=site.id).first()
    ai_config = ClientConfig.query.filter_by(site_id=site.id, key="ai_mode").first()
    ai_enabled = ai_config.value == "on" if ai_config else False
    if not branding:
        return jsonify({
            "bot_name": "ChatBot",
            "primary_color": "#667eea",
            "initial_message": "How can I help?",
            "theme_mode": "light",
            "ai_enabled": ai_enabled
        })
    data = branding.to_dict()
    data["ai_enabled"] = ai_enabled
    return jsonify(data)

@app.route("/widget/init.html")
def widget_init():
    site_id = request.args.get("site_id", 1, type=int)
    branding = BrandingSettings.query.filter_by(site_id=site_id).first() or BrandingSettings.query.first()
    site = db.session.get(Site, site_id)
    api_url = request.args.get("api", "http://localhost:5000")
    return render_template("widget.html", api_url=api_url, branding=branding, site=site)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session["admin_id"] = admin.id
            session["site_id"] = getattr(admin, "site_id", None)
            session.permanent = True
            if getattr(admin, "is_super", False):
                return redirect(url_for("super_dashboard"))
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="Invalid credentials")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/super/dashboard")
@login_required
def super_dashboard():
    admin = db.session.get(Admin, session.get("admin_id"))
    if not admin or not admin.is_super:
        return "Access Denied", 403
    return render_template("super_dashboard.html")

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    site_id = session.get("site_id")
    site = db.session.get(Site, site_id) if site_id else None
    api_url = request.url_root.rstrip("/")
    return render_template("admin_dashboard.html", site=site, site_id=site_id, widget_url=WIDGET_EMBED_URL, api_url=api_url)

@app.route("/api/base-url")
def get_base_url():
    return {"base_url": request.url_root.rstrip("/")}

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    print("AI Chatbot Server Running on http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=DEBUG)