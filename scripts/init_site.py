"""
init_site.py: Quickly create a first site and admin for ChatbotX platform.

Usage:
    python scripts/init_site.py --site "Acme Corp" --admin "admin" --password "admin123" --domain "acme.com"

If arguments are omitted, defaults will be used.
"""
import sys
from pathlib import Path

# Parse args
import argparse
parser = argparse.ArgumentParser(description="Initialize first site and admin.")
parser.add_argument('--site', type=str, default="Acme Corp", help='Site name')
parser.add_argument('--admin', type=str, default="admin", help='Admin username')
parser.add_argument('--password', type=str, default="admin123", help='Admin password')
parser.add_argument('--domain', type=str, default="acme.com", help='Domain (optional)')
args = parser.parse_args()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from database import db
from models import Site, Admin

with app.app_context():
    # Check if site exists
    site = Site.query.filter_by(name=args.site).first()
    if not site:
        site = Site(name=args.site, domain=args.domain, status="active", bot_name=f"{args.site} Bot")
        db.session.add(site)
        db.session.flush()
        print(f"Created site: {site.name} (ID: {site.id})")
    else:
        print(f"Site already exists: {site.name} (ID: {site.id})")

    # Check if admin exists
    admin = Admin.query.filter_by(username=args.admin).first()
    if not admin:
        admin = Admin(username=args.admin, site_id=site.id, is_super=True)
        admin.set_password(args.password)
        db.session.add(admin)
        print(f"Created admin: {admin.username} (site_id: {site.id})")
    else:
        # Link admin to site if not already
        if not admin.site_id:
            admin.site_id = site.id
            print(f"Linked admin {admin.username} to site {site.id}")
        print(f"Admin already exists: {admin.username} (site_id: {admin.site_id})")

    db.session.commit()
    print("Initialization complete.")
