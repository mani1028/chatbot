#!/usr/bin/env python
"""Create test site for validation"""
from app import app
from models import db
from models.site import Site

with app.app_context():
    # Try to find existing test site
    existing = Site.query.filter_by(public_key='kernel_test_key').first()
    if existing:
        print(f"EXISTING: id={existing.id}, public_key={existing.public_key}")
    else:
        # Create new site
        site = Site(name='Kernel Test', public_key='kernel_test_key')
        db.session.add(site)
        db.session.commit()
        print(f"CREATED: id={site.id}, public_key={site.public_key}")
