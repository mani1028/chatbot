from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from functools import wraps
from datetime import datetime

# Config
from config import (
    SECRET_KEY,
    DEBUG,
    SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    DEFAULT_BRANDING,
    WIDGET_EMBED_URL
)

# Database
from database import db, init_db
from models import (
    Admin,
    BrandingSettings,
    Site,
    Plan,
    ClientConfig
)

# Blueprints
from routes.chat_routes import chat_bp
from routes.admin_api import admin_api

# ---------------------------------------------------
# APP INIT
# ---------------------------------------------------
app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

db.init_app(app)

# ---------------------------------------------------
# LOGIN REQUIRED DECORATOR
# ---------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------
# DATABASE INIT + SEEDING
# ---------------------------------------------------
with app.app_context():
    init_db(app)

    # Create Super Admin
    super_admin = Admin.query.filter_by(username=ADMIN_USERNAME).first()
    if not super_admin:
        super_admin = Admin(username=ADMIN_USERNAME, is_super=True)
        super_admin.set_password(ADMIN_PASSWORD)
        db.session.add(super_admin)
        db.session.commit()

    # Seed Plans
    if Plan.query.count() == 0:
        plans = [
            Plan(name="Free Tier", max_monthly_chats=100, price=0.0),
            Plan(name="Starter", max_monthly_chats=1000, price=29.0),
            Plan(name="Pro", max_monthly_chats=10000, price=99.0),
            Plan(name="Enterprise", max_monthly_chats=100000, price=499.0)
        ]
        db.session.add_all(plans)
        db.session.commit()


    # Default Site (DISABLED)
    # if not db.session.get(Site, 1):
    #     starter = Plan.query.filter_by(name="Starter").first()
    #     site = Site(
    #         name="Platform Demo",
    #         domain="localhost",
    #         bot_name="Demo Bot",
    #         plan_id=starter.id if starter else None
    #     )
    #     db.session.add(site)
    #     db.session.commit()
    #
    #     super_admin.site_id = site.id
    #     db.session.commit()

    # Default Branding (Attach to Site 1)
    default_site = db.session.get(Site, 1)

    if default_site:
        existing_branding = BrandingSettings.query.filter_by(site_id=default_site.id).first()

        if not existing_branding:
            branding = BrandingSettings(
                site_id=default_site.id,
                **DEFAULT_BRANDING
            )
            db.session.add(branding)
            db.session.commit()


# ---------------------------------------------------
# REGISTER BLUEPRINTS
# ---------------------------------------------------
app.register_blueprint(chat_bp)
app.register_blueprint(admin_api, url_prefix="/admin/api")


# ---------------------------------------------------
# PUBLIC ROUTES
# ---------------------------------------------------
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
    site_id = request.args.get("site_id", 1, type=int)
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()

    ai_config = ClientConfig.query.filter_by(site_id=site_id, key="ai_mode").first()
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

# Locate widget_init() and update the final return line:
@app.route("/widget/init.html")
def widget_init():
    site_id = request.args.get("site_id", 1, type=int)
    branding = BrandingSettings.query.filter_by(site_id=site_id).first()
    
    if not branding:
         branding = BrandingSettings.query.first()
         
    api_url = request.args.get("api", "http://localhost:5000")
    
    # FIX: Explicitly pass site_id=site_id to the template
    return render_template("widget.html", api_url=api_url, branding=branding, site_id=site_id)

# ---------------------------------------------------
# AUTH
# ---------------------------------------------------
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


# ---------------------------------------------------
# DASHBOARDS
# ---------------------------------------------------
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
    # Pass the widget_url to the template
    from flask import request
    site_id = session.get("site_id")
    site = None
    if site_id:
        site = Site.query.get(site_id)
    # Dynamically determine the base API URL
    api_url = request.url_root.rstrip("/")
    return render_template(
        "admin_dashboard.html",
        site=site,
        site_id=site_id,
        widget_url=WIDGET_EMBED_URL,
        api_url=api_url
    )

# Utility route to fetch the current base URL
@app.route("/api/base-url")
def get_base_url():
    # This returns the base URL as seen by the client/browser
    from flask import request
    return {"base_url": request.url_root.rstrip("/")}
# ---------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    print("AI Chatbot Server Running on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=DEBUG)
