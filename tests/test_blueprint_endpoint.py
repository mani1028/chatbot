#!/usr/bin/env python
"""Test blueprint endpoint to verify it's working"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.intent import Intent

def test_blueprint_endpoint():
    """Test GET /admin/api/super/blueprints"""
    print("\n[TEST] Blueprint Endpoint Test")
    print("=" * 60)
    
    with app.app_context():
        client = app.test_client()
        
        print("\n[1] Testing: GET /admin/api/super/blueprints")
        
        response = client.get('/admin/api/super/blueprints')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_json()
            print(f"✓ Endpoint returned 200 OK")
            print(f"\nResponse structure:")
            print(f"  - blueprints: {len(data.get('blueprints', []))} items")
            print(f"  - grouped: {len(data.get('grouped', []))} templates")
            
            # Show sample blueprint if available
            blueprints = data.get('blueprints', [])
            if blueprints:
                print(f"\n✓ Found {len(blueprints)} blueprints")
                print(f"\nSample blueprint #1:")
                bp = blueprints[0]
                print(f"  ID: {bp.get('id')}")
                print(f"  Name: {bp.get('name')}")
                print(f"  Type: {bp.get('intent_type')}")
                print(f"  Category: {bp.get('category')}")
                print(f"  Phrases: {bp.get('phrases', [])[:3]}")
                print(f"  Response (first 100 chars): {bp.get('response', '')[:100]}")
            else:
                print("\n⚠ No blueprints found in database")
                print("  This is OK - blueprints need to be created first")
                print("  Blueprints are created by admins and stored with site_id=0")
                
        elif response.status_code == 401:
            print(f"✗ Got 401 Unauthorized - This endpoint requires super_admin authentication")
            print(f"  To test: Need to login as super admin first or use a session")
            
        else:
            print(f"✗ Got status code: {response.status_code}")
            try:
                print(f"Response: {response.get_json()}")
            except:
                print(f"Response: {response.data[:500]}")
        
        # Check what blueprints exist in database
        print("\n[2] Checking database for blueprints (site_id=0)")
        blueprint_count = Intent.query.filter_by(site_id=0).count()
        print(f"Found {blueprint_count} blueprint intents in database")
        
        if blueprint_count > 0:
            bp = Intent.query.filter_by(site_id=0).first()
            print(f"\nFirst blueprint:")
            print(f"  ID: {bp.id}")
            print(f"  Name: {bp.intent_name}")
            print(f"  Type: {bp.intent_type}")
            print(f"  Sector: {bp.sector}")
            print(f"  Phrases: {len(bp.phrases.all())} total")
        
    print("\n" + "="*60)

if __name__ == "__main__":
    test_blueprint_endpoint()
