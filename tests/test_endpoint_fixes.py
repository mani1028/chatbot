#!/usr/bin/env python
"""Test the fixed endpoints"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.site import Site
from database import db

with app.app_context():
    print("\n" + "="*60)
    print("TESTING FIXED ENDPOINTS")
    print("="*60)
    
    client = app.test_client()
    
    # Get a test site
    test_site = Site.query.first()
    if not test_site:
        print("❌ No test site found - creating one")
        test_site = Site(name="test", public_key="pk_test_12345")
        db.session.add(test_site)
        db.session.commit()
    
    print(f"\n✓ Using test site: {test_site.name} (public_key: {test_site.public_key})")
    
    # Test 1: Public site-features endpoint
    print("\n[1] Testing /admin/api/site-features (public endpoint with site_key)")
    res = client.get(f'/admin/api/site-features?site_key={test_site.public_key}')
    if res.status_code == 200:
        print("  ✅ PASS - Endpoint works with site_key!")
        data = res.get_json()
        print(f"    Features returned: {list(data.keys())[:3]}...")
    else:
        print(f"  ❌ FAIL - Status: {res.status_code}")
        print(f"    Error: {res.get_json()}")
    
    # Test 2: Invalid site_key
    print("\n[2] Testing /admin/api/site-features with invalid site_key")
    res = client.get('/admin/api/site-features?site_key=pk_invalid_000')
    if res.status_code == 404:
        print("  ✅ PASS - Returns 404 for invalid site_key")
    else:
        print(f"  ❌ FAIL - Status: {res.status_code}")
    
    # Test 3: Missing site_key
    print("\n[3] Testing /admin/api/site-features without site_key")
    res = client.get('/admin/api/site-features')
    if res.status_code == 400:
        print("  ✅ PASS - Returns 400 for missing site_key")
    else:
        print(f"  ❌ FAIL - Status: {res.status_code}")
    
    # Test 4: Client channels endpoint
    print("\n[4] Testing /admin/api/client/channels (fixed)")
    res = client.get('/admin/api/client/channels')
    if res.status_code == 401:
        print("  ✅ PASS - Auth check works (401 expected without session)")
    elif res.status_code == 200:
        data = res.get_json()
        print("  ✅ PASS - Endpoint returned channels")
        print(f"    Channels: {data.get('channels', [])}")
    else:
        print(f"  ❌ FAIL - Status: {res.status_code}")
        print(f"    Error: {res.get_json()}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60 + "\n")
