#!/usr/bin/env python
"""Test the new /api/site-features endpoint."""

import os
import sys
import json
from app import app, db
from models.site import Site

# Initialize Flask app context
with app.app_context():
    print("=" * 60)
    print("TESTING /api/site-features ENDPOINT")
    print("=" * 60)
    
    # Create test client
    client = app.test_client()
    
    # Get a site with public_key
    site = Site.query.first()
    if not site:
        print("❌ No sites found in database!")
        sys.exit(1)
    
    print(f"\n✓ Found test site: {site.name} (public_key: {site.public_key})")
    
    # Test the endpoint
    print(f"\n[TEST 1] Fetching /api/site-features?site_key={site.public_key}")
    response = client.get(f'/api/site-features?site_key={site.public_key}')
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.get_json()
        print(f"Response: {json.dumps(data, indent=2)}")
        print("✅ Endpoint works correctly!")
    else:
        print(f"❌ Error: {response.get_json()}")
    
    # Test with invalid site_key
    print(f"\n[TEST 2] Fetching with invalid site_key")
    response = client.get('/api/site-features?site_key=pk_invalid_000')
    print(f"Status: {response.status_code}")
    if response.status_code == 404:
        print(f"✅ Correctly returns 404 for invalid site_key")
    else:
        print(f"❌ Expected 404, got {response.status_code}")
    
    # Test without site_key
    print(f"\n[TEST 3] Fetching without site_key parameter")
    response = client.get('/api/site-features')
    print(f"Status: {response.status_code}")
    if response.status_code == 400:
        print(f"✅ Correctly returns 400 for missing site_key")
    else:
        print(f"❌ Expected 400, got {response.status_code}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
