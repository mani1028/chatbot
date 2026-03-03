#!/usr/bin/env python3
"""
PASS 1: Telemetry Insert Validation
- Start app minimally
- Send 20 real HTTP requests
- Query metrics table
- Report numbers (no interpretation)
"""

import sys
import sqlite3
import time
import uuid
import json
import threading
from datetime import datetime
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'chatbot.db')

def setup_app_minimal():
    """Setup app with minimal initialization, avoiding HuggingFace"""
    print("Initializing app minimally...")
    
    from app import create_app
    from database import db
    from models import Site, Plan
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Get or create test site
        test_site = Site.query.filter_by(name='PASS1 Validation').first()
        
        if not test_site:
            plan = Plan.query.first()
            if not plan:
                plan = Plan(
                    name='Test Plan',
                    max_monthly_chats=10000,
                    max_concurrent_users=100
                )
                db.session.add(plan)
                db.session.commit()
            
            test_site = Site(
                name='PASS1 Validation',
                public_key=str(uuid.uuid4())[:32],
                plan_id=plan.id,
                tenant_id=1,
                custom_domain='localhost:5000',
                widget_enabled=True,
                created_at=datetime.utcnow()
            )
            db.session.add(test_site)
            db.session.commit()
        
        return app, test_site.public_key


def start_app_server(app):
    """Start Flask app in background thread"""
    print("Starting Flask server...")
    
    def run():
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
    
    server_thread = threading.Thread(target=run, daemon=True)
    server_thread.start()
    
    # Wait for server to start
    time.sleep(3)
    print("✓ Server started on port 5000")


def send_http_requests(site_key, count=20):
    """Send N real HTTP requests"""
    import requests
    
    print(f"\nSending {count} real HTTP requests...")
    
    messages = [
        'Book an appointment',
        'How much does it cost?',
        'I need technical support',
        'Can I order this?',
        'What are your hours?',
        'I have a question',
        'Help me please',
        'Is this available?',
        'I want to cancel',
        'How do I get started?',
    ]
    
    successful = 0
    
    for i in range(count):
        try:
            message = messages[i % len(messages)]
            session_id = str(uuid.uuid4())
            
            payload = {
                'site_key': site_key,
                'message': message,
                'session_id': session_id,
                'page_url': 'http://localhost/test'
            }
            
            response = requests.post(
                'http://localhost:5000/api/chat',
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                successful += 1
                print(f"  [{i+1:2d}/{count}] ✓ {response.status_code}", end='\r')
            else:
                print(f"  [{i+1:2d}/{count}] ✗ {response.status_code}")
        except Exception as e:
            print(f"  [{i+1:2d}/{count}] ✗ Error: {str(e)[:50]}")
        
        time.sleep(0.1)
    
    print(f"\n✓ Sent {successful}/{count} successful requests")
    return successful


def query_metrics_table():
    """Query phase1_metrics and return results"""
    print("\nQuerying phase1_metrics table...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Wait for any pending commits
        time.sleep(2)
        
        # Query 1: Total count
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics WHERE phase_version = '1.0.0'")
        total = cursor.fetchone()[0]
        
        # Query 2: Recent inserts (last 5 minutes)
        cursor.execute("""
            SELECT COUNT(*) FROM phase1_metrics 
            WHERE phase_version = '1.0.0'
            AND datetime(timestamp) > datetime('now', '-5 minutes')
        """)
        recent = cursor.fetchone()[0]
        
        # Query 3: Confidence band distribution
        cursor.execute("""
            SELECT confidence_band, COUNT(*) 
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
            GROUP BY confidence_band
        """)
        bands = cursor.fetchall()
        
        # Query 4: Clarification triggered
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN clarification_triggered THEN 1 END) as triggered,
                COUNT(CASE WHEN llm_called THEN 1 END) as llm_called
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        triggered, llm_called = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_rows': total,
            'recent_rows': recent,
            'confidence_bands': bands,
            'clarification_triggered': triggered,
            'llm_called': llm_called
        }
        
    except Exception as e:
        print(f"✗ Query failed: {e}")
        return None


def check_health_endpoint():
    """Check /health endpoint"""
    print("\nChecking /health endpoint...")
    
    try:
        import requests
        response = requests.get('http://localhost:5000/health', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"✗ Health check returned {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return None


def main():
    print("=" * 80)
    print("PASS 1: TELEMETRY INSERT VALIDATION")
    print("=" * 80)
    
    try:
        # Step 1: Setup
        print("\n1️⃣  SETUP PHASE")
        print("-" * 80)
        app, site_key = setup_app_minimal()
        start_app_server(app)
        
        # Step 2: Send traffic
        print("\n2️⃣  TRAFFIC PHASE")
        print("-" * 80)
        successful = send_http_requests(site_key, count=20)
        
        if successful == 0:
            print("\n❌ No successful requests sent. Cannot continue validation.")
            return False
        
        # Step 3: Query results
        print("\n3️⃣  VALIDATION PHASE")
        print("-" * 80)
        metrics = query_metrics_table()
        
        if not metrics:
            print("\n❌ Could not query metrics table")
            return False
        
        # Step 4: Health check
        health = check_health_endpoint()
        
        # Step 5: Report findings
        print("\n" + "=" * 80)
        print("PASS 1 RESULTS - RAW NUMBERS")
        print("=" * 80)
        
        print(f"\n📊 HTTP Traffic:")
        print(f"  Requests sent:          {successful}/20")
        
        print(f"\n📈 Metrics Inserted:")
        print(f"  Total rows in table:    {metrics['total_rows']}")
        print(f"  Recent insertions (5m): {metrics['recent_rows']}")
        
        print(f"\n🎯 Confidence Bands:")
        for band, count in metrics['confidence_bands']:
            print(f"  {band:8s}:  {count}")
        
        print(f"\n⚡ Clarification & LLM:")
        print(f"  Clarification triggered: {metrics['clarification_triggered']}")
        print(f"  LLM called:              {metrics['llm_called']}")
        
        if health:
            print(f"\n❤️  Health Endpoint:")
            print(f"  Status:                 {health.get('status')}")
            telemetry = health.get('telemetry', {})
            print(f"  Telemetry healthy:      {telemetry.get('telemetry_healthy')}")
            print(f"  Metrics failures:       {telemetry.get('metrics_failures')}")
        
        print("\n" + "=" * 80)
        print("PASS 1 COMPLETE")
        print("=" * 80)
        
        # Assessment
        if metrics['total_rows'] >= successful * 0.9:  # At least 90% of requests logged
            print("\n✅ PASS 1 VERDICT: Telemetry is inserting correctly")
            return True
        else:
            print(f"\n⚠️  PASS 1 VERDICT: Only {metrics['total_rows']}/{successful} requests logged")
            return False
            
    except Exception as e:
        print(f"\n❌ PASS 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
