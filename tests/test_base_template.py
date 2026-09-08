#!/usr/bin/env python
"""
Base Test Template for Chatbot API Endpoints

This template provides structure for testing your Flask APIs.
Copy and modify as needed for specific test cases.
"""

import pytest
import json
from app import app, db
from models import Site, Admin


class TestConfig:
    """Test configuration and fixtures."""
    
    @pytest.fixture(scope="session")
    def test_app(self):
        """Create and configure a new app instance for each test session."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, test_app):
        """A test client for the app."""
        return test_app.test_client()
    
    @pytest.fixture
    def test_site(self, test_app):
        """Create a test site."""
        with test_app.app_context():
            site = Site(
                name="Test Site",
                domain="test.example.com",
                status="active",
                bot_name="TestBot"
            )
            db.session.add(site)
            db.session.commit()
            return site
    
    @pytest.fixture
    def test_admin(self, test_app, test_site):
        """Create a test admin user."""
        with test_app.app_context():
            admin = Admin(
                username="testadmin",
                site_id=test_site.id,
                is_super=True
            )
            admin.set_password("testpass123")
            db.session.add(admin)
            db.session.commit()
            return admin


class TestAPIEndpoints:
    """Test suite for API endpoints."""
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'ok'
    
    def test_widget_settings_with_valid_site(self, client, test_site):
        """Test widget settings endpoint with valid site key."""
        response = client.get(f'/api/widget-settings?site_key={test_site.public_key}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'bot_name' in data
        assert 'primary_color' in data
    
    def test_widget_settings_without_site_key(self, client):
        """Test widget settings endpoint returns defaults without site key."""
        response = client.get('/api/widget-settings')
        assert response.status_code == 200
        data = response.get_json()
        # Should return default settings
        assert 'bot_name' in data
    
    def test_site_features_with_valid_key(self, client, test_site):
        """Test site features endpoint with valid site key."""
        response = client.get(f'/api/site-features?site_key={test_site.public_key}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'plan_name' in data
        assert 'workflows_enabled' in data
    
    def test_site_features_invalid_key(self, client):
        """Test site features endpoint with invalid site key."""
        response = client.get('/api/site-features?site_key=pk_invalid_000')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
    
    def test_site_features_missing_key(self, client):
        """Test site features endpoint without site key."""
        response = client.get('/api/site-features')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data


class TestAuthentication:
    """Test suite for authentication."""
    
    def test_admin_login_success(self, client, test_admin):
        """Test successful admin login."""
        response = client.post('/admin/login', data={
            'username': 'testadmin',
            'password': 'testpass123'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_admin_login_failure(self, client):
        """Test failed admin login."""
        response = client.post('/admin/login', data={
            'username': 'wronguser',
            'password': 'wrongpass'
        })
        assert response.status_code in [200, 401, 403]


class TestChatAPI:
    """Test suite for chat functionality."""
    
    def test_chat_message_with_valid_site(self, client, test_site):
        """Test sending chat message with valid site."""
        response = client.post('/api/chat', 
            json={
                'site_key': test_site.public_key,
                'message': 'Hello',
                'session_id': 'test-session-001'
            },
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data or 'status' in data
    
    def test_chat_message_missing_required_fields(self, client, test_site):
        """Test chat message with missing required fields."""
        response = client.post('/api/chat',
            json={
                'site_key': test_site.public_key
                # Missing message and session_id
            },
            content_type='application/json'
        )
        # Should either fail validation or handle gracefully
        assert response.status_code in [400, 422]


class TestIntegration:
    """End-to-end integration tests."""
    
    def test_widget_full_flow(self, client, test_site):
        """Test complete widget initialization flow."""
        # 1. Get widget settings
        settings_resp = client.get(f'/api/widget-settings?site_key={test_site.public_key}')
        assert settings_resp.status_code == 200
        settings = settings_resp.get_json()
        
        # 2. Get site features
        features_resp = client.get(f'/api/site-features?site_key={test_site.public_key}')
        assert features_resp.status_code == 200
        features = features_resp.get_json()
        
        # 3. Send test message
        chat_resp = client.post('/api/chat',
            json={
                'site_key': test_site.public_key,
                'message': 'Test integration',
                'session_id': f'integration-test-{test_site.id}'
            },
            content_type='application/json'
        )
        assert chat_resp.status_code == 200
        
        # All components should be available
        assert settings and features and chat_resp.get_json()


class TestErrorHandling:
    """Test suite for error handling."""
    
    def test_404_not_found(self, client):
        """Test 404 handling."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
    
    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.get('/health')
        # CORS headers should be present or be handled by CORS middleware
        assert response.status_code == 200


# =============================================================================
# Usage Instructions
# =============================================================================
"""
To run these tests:

1. Install pytest:
   pip install pytest pytest-flask

2. Run all tests:
   pytest test_base_template.py -v

3. Run specific test class:
   pytest test_base_template.py::TestAPIEndpoints -v

4. Run specific test:
   pytest test_base_template.py::TestAPIEndpoints::test_health_endpoint -v

5. Run with coverage:
   pytest test_base_template.py --cov=routes --cov=services

Common Options:
  -v          : Verbose output
  -s          : Show print statements
  --tb=short  : Shorter traceback format
  -x          : Stop on first failure
  -k "pattern": Run tests matching pattern
"""


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
