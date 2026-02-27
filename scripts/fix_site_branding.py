# Script to check/fix site_id and BrandingSettings for all sites and admins
# Usage: python scripts/fix_site_branding.py


import sys
from pathlib import Path
# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from database import db
from models import Site, Admin, BrandingSettings

def ensure_branding(site):
    branding = BrandingSettings.query.filter_by(site_id=site.id).first()
    if not branding:
        branding = BrandingSettings(
            site_id=site.id,
            bot_name="Apollo Assistant",
            initial_message="Hello! How can I help you?",
            primary_color="#6366f1",
            theme_mode="light",
            position="bottom-right"
        )
        db.session.add(branding)
        print(f"Created default BrandingSettings for site_id={site.id}")

def ensure_admin_site_id(admin):
    if not admin.site_id:
        # Assign to first site if exists
        site = Site.query.first()
        if site:
            admin.site_id = site.id
            print(f"Assigned site_id={site.id} to admin id={admin.id}")

with app.app_context():
    # Fix admins
    admins = Admin.query.all()
    for admin in admins:
        ensure_admin_site_id(admin)
    db.session.commit()

    # Fix branding for all sites
    sites = Site.query.all()
    for site in sites:
        ensure_branding(site)
    db.session.commit()

print("Site_id and BrandingSettings check/fix complete.")
