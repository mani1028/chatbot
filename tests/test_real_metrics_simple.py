#!/usr/bin/env python3
"""
Real HTTP Metrics Test - Simplified Version
Uses Flask development server instead of production server.
"""

import requests
import sqlite3
import time
import uuid
import os
import sys
import threading
from datetime import datetime
from app import create_app
from database import db
from models import Site, Plan

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'chatbot.db')
API_BASE_URL = 'http://localhost:5000/api/chat'
TOTAL_REQUESTS = 100

# Test messages
TEST_INTENTS = [
    'I want to book an appointment',
    'Can I order something?',
    'How much does this cost?',
    'I need to change my password',
    'Is this available?',
    'Hello',
    'What do you do?',
    'How do I get help?',
    'I have a question',
    'Can you help?',
]

def setup_and_run_app():
    """Setup database and start Flask app in background"""
    print("Setting up application...")
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        print("  • Creating database tables...")
        db.create_all()
        
        # Get or create test site
        print("  • Setting up test site...")
        test_site = Site.query.filter_by(name='Real Traffic Test').first()
        
        if not test_site:
            # Get or create plan
            plan = Plan.query.first()
            if not plan:
                plan = Plan(
                    name='Test Plan',
                    max_monthly_chats=10000,
                    max_concurrent_users=100
                )
                db.session.add(plan)
                db.session.commit()
            
            # Create site
            test_site_key = str(uuid.uuid4())[:32]
            test_site = Site(
                name='Real Traffic Test',
                public_key=test_site_key,
                plan_id=plan.id,
                tenant_id=1,
                custom_domain='localhost:5000',
                widget_enabled=True,
                created_at=datetime.utcnow()
            )
            db.session.add(test_site)
            db.session.commit()
        
        print(f"  ✓ Test site created/found: {test_site.name}")
        
        # Start Flask in separate thread
        def run_app():
            print("  ✓ Starting Flask development server...")
            app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
        
        server_thread = threading.Thread(target=run_app, daemon=True)
        server_thread.start()
        
        # Wait for server to start
        time.sleep(3)
        
        return test_site.public_key


def send_traffic(site_key):
    """Send 100 HTTP requests"""
    print(f"\nSending {TOTAL_REQUESTS} HTTP requests...")
    
    successful = 0
    
    for i in range(TOTAL_REQUESTS):
        try:
            message = TEST_INTENTS[i % len(TEST_INTENTS)]
            session_id = str(uuid.uuid4())
            
            payload = {
                'site_key': site_key,
                'message': message,
                'session_id': session_id,
                'page_url': 'http://localhost/test'
            }
            
            response = requests.post(API_BASE_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                successful += 1
            
            if (i + 1) % 10 == 0:
                print(f"  • Sent {i + 1}/{TOTAL_REQUESTS}", end='\r')
            
            time.sleep(0.05)  # Small delay
            
        except Exception as e:
            pass
    
    print(f"  ✓ Completed: {successful}/{TOTAL_REQUESTS} successful")
    return successful


def check_metrics(requests_sent):
    """Check phase1_metrics table"""
    print("\n" + "=" * 80)
    print("REAL HTTP METRICS - VALIDATION RESULTS")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Wait for commits
        time.sleep(2)
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics WHERE phase_version = '1.0.0'")
        result = cursor.fetchone()
        
        if not result:
            print("\n❌ NO METRICS TABLE - query failed!")
            conn.close()
            return None
        
        total_rows = result[0]
        
        print(f"\n🔢 COUNTS:")
        print(f"   HTTP requests sent:       {requests_sent}")
        print(f"   Metrics rows in DB:       {total_rows}")
        
        if total_rows == 0:
            print("\n   ❌ CRITICAL: No metrics logged!")
            print("   The orchestrator logging is NOT working.")
            conn.close()
            return None
        
        if total_rows == requests_sent:
            print(f"   ✅ PERFECT MATCH - all requests logged")
        else:
            pct = (total_rows / requests_sent * 100)
            print(f"   ⚠️  {pct:.1f}% of requests logged")
        
        # Confidence bands
        cursor.execute("""
            SELECT confidence_band, COUNT(*) as count
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
            GROUP BY confidence_band
        """)
        
        bands = cursor.fetchall()
        print(f"\n📊 CONFIDENCE BANDS:")
        for band, count in bands:
            pct = (count / total_rows * 100) if total_rows > 0 else 0
            print(f"   {band:8s}:  {count:4d} ({pct:5.1f}%)")
        
        # Clarification
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN clarification_triggered THEN 1 END) as triggered,
                COUNT(CASE WHEN clarification_confirmed THEN 1 END) as confirmed
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        total, triggered, confirmed = cursor.fetchone()
        trigger_pct = (triggered / total * 100) if total > 0 else 0
        confirm_pct = (confirmed / triggered * 100) if triggered > 0 else 0
        
        print(f"\n🎯 CLARIFICATION:")
        print(f"   Total:       {total}")
        print(f"   Triggered:   {triggered} ({trigger_pct:.1f}%)")
        print(f"   Confirmed:   {confirmed} ({confirm_pct:.1f}% of triggered)" if triggered > 0 else "")
        
        # LLM
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN llm_called THEN 1 END) as llm_count
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        total, llm_count = cursor.fetchone()
        llm_pct = (llm_count / total * 100) if total > 0 else 0
        reduction = ((total - llm_count) / total * 100) if total > 0 else 0
        
        print(f"\n⚡ LLM INVOCATIONS:")
        print(f"   Total:       {total}")
        print(f"   LLM called:  {llm_count} ({llm_pct:.1f}%)")
        print(f"   Reduction:   {reduction:.1f}%")
        
        # Response time
        cursor.execute("""
            SELECT ROUND(AVG(total_response_time_ms), 2)
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        avg_ms = cursor.fetchone()[0]
        print(f"\n⏱️  RESPONSE TIME:")
        print(f"   Average:     {avg_ms} ms")
        
        conn.close()
        
        return {
            'total_rows': total_rows,
            'requests_sent': requests_sent,
            'trigger_pct': trigger_pct,
            'confirm_pct': confirm_pct,
            'reduction_pct': reduction,
            'avg_ms': avg_ms
        }
        
    except Exception as e:
        print(f"\n❌ Error querying metrics: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("REAL HTTP METRICS VALIDATION")
    print("=" * 80)
    
    try:
        # Setup and start app
        print("\n1️⃣  SETUP PHASE")
        print("-" * 80)
        site_key = setup_and_run_app()
        
        # Send traffic
        print("\n2️⃣  TRAFFIC PHASE")
        print("-" * 80)
        requests_sent = send_traffic(site_key)
        
        # Check metrics
        print("\n3️⃣  VALIDATION PHASE")
        print("-" * 80)
        metrics = check_metrics(requests_sent)
        
        # Assessment
        print("\n" + "=" * 80)
        if metrics and metrics['total_rows'] > 0:
            print("✅ TELEMETRY WORKING - Metrics are being logged")
            print("=" * 80)
            print("\n5️⃣  KEY NUMBERS (from real HTTP traffic):")
            print(f"   1. Total rows inserted:     {metrics['total_rows']}")
            print(f"   2. Trigger rate:             {metrics['trigger_pct']:.1f}%")
            print(f"   3. Confirmation rate:        {metrics['confirm_pct']:.1f}%" if metrics['confirm_pct'] else "")
            print(f"   4. LLM reduction:            {metrics['reduction_pct']:.1f}%")
            print(f"   5. Avg response time:        {metrics['avg_ms']} ms")
            return True
        else:
            print("❌ TELEMETRY NOT WORKING - No metrics recorded")
            print("=" * 80)
            print("\nThe orchestrator is NOT calling Phase1Metrics logging.")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
