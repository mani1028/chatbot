#!/usr/bin/env python
"""
Setup test environment for load testing.
Creates a test site with valid configuration so load tests can run.
"""
import sys
sys.path.insert(0, '/c/Users/HP/OneDrive/Desktop/chatbot')

from app import app, db
from models.plan import Plan
from models.site import Site
from datetime import datetime

def setup_test_environment():
    """Create test site and configuration for load testing."""
    print("=" * 80)
    print("[SETUP] Creating Test Environment")
    print("=" * 80)
    
    with app.app_context():
        # Create test plan
        print("[*] Creating test plan...")
        test_plan = Plan.query.filter_by(name='TestPlan').first()
        if not test_plan:
            test_plan = Plan(name='TestPlan', max_monthly_chats=100000)
            db.session.add(test_plan)
            db.session.commit()
            print(f"    ✓ Plan created: {test_plan.id}")
        else:
            print(f"    ✓ Plan exists: {test_plan.id}")
        
        # Create test site
        print("[*] Creating test site...")
        test_site = Site.query.filter_by(public_key='test-site-key').first()
        if not test_site:
            test_site = Site(
                name='Test Site for Load Testing',
                public_key='test-site-key',
                domain='localhost',
                status='active',
                plan_id=test_plan.id
            )
            db.session.add(test_site)
            db.session.commit()
            print(f"    ✓ Site created: {test_site.id}")
            print(f"    ✓ Public Key: test-site-key")
        else:
            print(f"    ✓ Site exists: {test_site.id}")
        
        # Verify site configuration
        print()
        print("Test Environment:")
        print(f"  Site ID: {test_site.id}")
        print(f"  Public Key: {test_site.public_key}")
        print(f"  Domain: {test_site.domain}")
        print(f"  Status: {test_site.status}")
        print(f"  Plan: {test_site.plan.name if test_site.plan else 'None'}")
        print()
        print("=" * 80)
        print("✓ Test environment ready. Run load_test.py to begin testing.")
        print("=" * 80)

if __name__ == '__main__':
    setup_test_environment()
