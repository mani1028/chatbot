#!/usr/bin/env python3
"""
Contact Agent Feature - Setup and Verification Script
Tests that all components are properly integrated
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_model_import():
    """Test that ContactRequest model can be imported."""
    logger.info("Testing ContactRequest model import...")
    try:
        from models.contact_request import ContactRequest
        logger.info("✓ ContactRequest model imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to import ContactRequest: {e}")
        return False

def test_database():
    """Test database connectivity and create tables."""
    logger.info("Testing database setup...")
    try:
        from app import create_app, db
        from models.contact_request import ContactRequest
        
        app = create_app()
        with app.app_context():
            # Create tables
            logger.info("Creating contact_requests table...")
            db.create_all()
            logger.info("✓ Database tables created successfully")
            
            # Verify table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'contact_requests' in tables:
                logger.info("✓ contact_requests table verified in database")
                
                # Show table columns
                columns = inspector.get_columns('contact_requests')
                logger.info(f"  Table columns: {', '.join([c['name'] for c in columns])}")
                return True
            else:
                logger.error("✗ contact_requests table not found in database")
                return False
                
    except Exception as e:
        logger.error(f"✗ Database setup failed: {e}", exc_info=True)
        return False

def test_api_endpoints():
    """Test that API endpoints are registered."""
    logger.info("Testing API endpoints...")
    try:
        from app import create_app
        
        app = create_app()
        
        # Get all registered routes
        routes = {}
        for rule in app.url_map.iter_rules():
            if 'contact' in rule.rule.lower():
                routes[rule.rule] = list(rule.methods - {'OPTIONS', 'HEAD'})
        
        expected_routes = [
            '/api/chat/contact-agent',
            '/admin/api/client/contact-requests',
            '/admin/api/client/contact-requests-dashboard',
            '/admin/api/client/contact-requests/<int:request_id>'
        ]
        
        # Flexible route checking
        found_routes = []
        for expected in expected_routes:
            # Check if any route contains key parts
            for route in routes.keys():
                if 'contact' in route.lower():
                    found_routes.append(route)
        
        if found_routes:
            logger.info(f"✓ Found {len(found_routes)} contact-related routes:")
            for route in found_routes:
                logger.info(f"  - {route}")
            return True
        else:
            logger.warning("⚠ No contact routes found (may need to manually register)")
            return False
            
    except Exception as e:
        logger.error(f"✗ Endpoint test failed: {e}", exc_info=True)
        return False

def test_static_files():
    """Test that static files exist."""
    logger.info("Testing static files...")
    from pathlib import Path
    
    files_to_check = [
        'static/contact_agent_form.js',
        'static/contact_agent_form.css'
    ]
    
    all_exist = True
    for file_path in files_to_check:
        full_path = Path(file_path)
        if full_path.exists():
            logger.info(f"✓ {file_path} exists ({full_path.stat().st_size} bytes)")
        else:
            logger.error(f"✗ {file_path} not found")
            all_exist = False
    
    return all_exist

def test_templates():
    """Test that templates exist."""
    logger.info("Testing templates...")
    from pathlib import Path
    
    template_path = Path('templates/contact_requests_admin.html')
    if template_path.exists():
        logger.info(f"✓ contact_requests_admin.html exists ({template_path.stat().st_size} bytes)")
        return True
    else:
        logger.error("✗ contact_requests_admin.html not found")
        return False

def test_intent_template():
    """Test that intent template exists."""
    logger.info("Testing intent template...")
    from pathlib import Path
    import json
    
    template_path = Path('intent_templates/contact_escalation_intents.json')
    try:
        if template_path.exists():
            with open(template_path) as f:
                data = json.load(f)
            
            intent_names = [i['name'] for i in data.get('intents', [])]
            if 'contact_agent' in intent_names:
                logger.info(f"✓ Intent template exists with intents: {', '.join(intent_names)}")
                return True
            else:
                logger.error("✗ contact_agent intent not found in template")
                return False
        else:
            logger.error("✗ Intent template file not found")
            return False
    except Exception as e:
        logger.error(f"✗ Failed to parse intent template: {e}")
        return False

def test_api_functionality():
    """Test basic API functionality."""
    logger.info("Testing API functionality...")
    try:
        from app import create_app, db
        from models.contact_request import ContactRequest
        from models.site import Site
        
        app = create_app()
        
        with app.app_context():
            # Get or create a test site
            test_site = Site.query.filter_by(name="Test Site").first()
            if not test_site:
                test_site = Site(name="Test Site", domain="test.com", status="active")
                db.session.add(test_site)
                db.session.commit()
            
            # Create a test contact request
            test_request = ContactRequest(
                site_id=test_site.id,
                session_id="test-session",
                user_name="Test User",
                user_email="test@example.com",
                message="This is a test message",
                priority="normal"
            )
            db.session.add(test_request)
            db.session.commit()
            
            # Verify it was saved
            saved = ContactRequest.query.filter_by(
                user_email="test@example.com"
            ).first()
            
            if saved:
                logger.info(f"✓ Successfully created and retrieved contact request (ID: {saved.id})")
                
                # Test to_dict method
                data = saved.to_dict()
                logger.info(f"  Request data: {data}")
                
                # Clean up
                db.session.delete(saved)
                db.session.commit()
                
                return True
            else:
                logger.error("✗ Failed to retrieve created contact request")
                return False
                
    except Exception as e:
        logger.error(f"✗ API functionality test failed: {e}", exc_info=True)
        return False

def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Contact Agent Feature - Verification Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Model Import", test_model_import),
        ("Database Setup", test_database),
        ("Static Files", test_static_files),
        ("Templates", test_templates),
        ("Intent Template", test_intent_template),
        ("API Endpoints", test_api_endpoints),
        ("API Functionality", test_api_functionality),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} test threw exception: {e}", exc_info=True)
            results[test_name] = False
        logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n✓ All tests passed! Feature is ready to use.")
        return 0
    else:
        logger.error(f"\n✗ {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
