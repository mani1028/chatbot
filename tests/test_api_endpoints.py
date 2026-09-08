#!/usr/bin/env python
"""Test API endpoints directly to check response format."""

import os
import sys
import json
from app import app, db

# Initialize Flask app context
with app.app_context():
    print("=" * 60)
    print("API ENDPOINT RESPONSE TEST")
    print("=" * 60)
    
    # Create test client
    client = app.test_client()
    
    # Test Unknown Intent List endpoint
    print("\n[GET /admin/api/unknown/list]")
    print("Testing without site_id filter...")
    response = client.get('/admin/api/unknown/list')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Response type: {type(data)}")
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        if 'unknowns' in data:
            print(f"Unknowns count: {len(data.get('unknowns', []))}")
            if data['unknowns']:
                print(f"Sample record: {json.dumps(data['unknowns'][0], indent=2)}")
    elif isinstance(data, list):
        print(f"Items count: {len(data)}")
        if data:
            print(f"Sample record: {json.dumps(data[0], indent=2)}")
    
    # Test with site_id
    print("\n\nTesting with site_id=7 (test_site)...")
    response = client.get('/admin/api/unknown/list?site_id=7')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    if isinstance(data, dict):
        if 'unknowns' in data:
            print(f"Unknowns count: {len(data.get('unknowns', []))}")
    elif isinstance(data, list):
        print(f"Items count: {len(data)}")
    
    # Test Billing endpoint
    print("\n\n[GET /admin/api/super/billing]")
    response = client.get('/admin/api/super/billing')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Response type: {type(data)}")
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        if 'billing' in data:
            print(f"Billing count: {len(data.get('billing', []))}")
            if data['billing']:
                print(f"Sample record: {json.dumps(data['billing'][0], indent=2)}")
    elif isinstance(data, list):
        print(f"Items count: {len(data)}")
        if data:
            print(f"Sample record: {json.dumps(data[0], indent=2)}")
    
    print("\n" + "=" * 60)
