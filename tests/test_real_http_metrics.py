#!/usr/bin/env python3
"""
Real HTTP Traffic Validation Test

This test:
1. Starts the Flask app
2. Creates a test site (or uses existing)
3. Sends 100 REAL HTTP requests
4. Queries the phase1_metrics table
5. Reports metrics for validation

This is NOT simulation. This is verification that the orchestrator
is actually calling Phase1Metrics.create_from_orchestrator().
"""

import requests
import json
import sqlite3
import time
import uuid
import os
import sys
import subprocess
import threading
from datetime import datetime

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'chatbot.db')
API_BASE_URL = 'http://localhost:5000/api/chat'
TOTAL_REQUESTS = 100

# Test messages with varying intent confidence
TEST_INTENTS = [
    {'message': 'I want to book an appointment', 'type': 'booking'},
    {'message': 'Can I order something?', 'type': 'order'},
    {'message': 'How much does this cost?', 'type': 'pricing'},
    {'message': 'I need to change my password', 'type': 'account'},
    {'message': 'Is this available?', 'type': 'availability'},
    {'message': 'Hello', 'type': 'greeting'},
    {'message': 'What do you do?', 'type': 'inquiry'},
    {'message': 'How do I get help?', 'type': 'support'},
    {'message': 'I have a question', 'type': 'vague'},
    {'message': 'Can you help?', 'type': 'vague'},
]

# Global app process
app_process = None
test_site_key = None


def start_flask_app():
    """Start Flask app in background"""
    global app_process
    
    print("Starting Flask app...")
    try:
        # Start app as subprocess
        app_process = subprocess.Popen(
            [sys.executable, 'run_production.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )
        
        # Wait for app to start
        time.sleep(3)
        
        # Verify it's running
        try:
            resp = requests.get('http://localhost:5000/health', timeout=2)
            print("✓ Flask app started on port 5000")
            return True
        except:
            # Try without /health endpoint, just ping the API
            try:
                resp = requests.get('http://localhost:5000/', timeout=2)
                print("✓ Flask app started on port 5000")
                return True
            except:
                print("✗ App failed to start")
                return False
    except Exception as e:
        print(f"✗ Failed to start app: {e}")
        return False


def stop_flask_app():
    """Stop Flask app"""
    global app_process
    if app_process:
        print("\nStopping Flask app...")
        app_process.terminate()
        try:
            app_process.wait(timeout=5)
        except:
            app_process.kill()
        print("✓ Flask app stopped")


def setup_test_site():
    """Get or create a test site with a public_key"""
    global test_site_key
    
    try:
        from config import SQLALCHEMY_DATABASE_URI
        from database import db
        from app import create_app
        from models import Site, Plan
        
        # Create app context
        app = create_app()
        
        with app.app_context():
            # Check if test site exists
            test_site = Site.query.filter_by(name='Test Site Real Traffic').first()
            
            if test_site:
                test_site_key = test_site.public_key
                print(f"✓ Using existing test site: {test_site.name}")
                print(f"  Public key: {test_site_key}")
                return True
            
            # Create new test site
            print("Creating test site...")
            
            # Get or create a plan
            plan = Plan.query.first()
            if not plan:
                plan = Plan(
                    name='Test Plan',
                    max_monthly_chats=10000,
                    max_concurrent_users=100
                )
                db.session.add(plan)
                db.session.commit()
            
            # Create site with unique public_key
            test_site_key = str(uuid.uuid4())[:32]
            test_site = Site(
                name='Test Site Real Traffic',
                public_key=test_site_key,
                plan_id=plan.id,
                tenant_id=1,
                custom_domain='localhost:5000',
                widget_enabled=True,
                created_at=datetime.utcnow()
            )
            
            db.session.add(test_site)
            db.session.commit()
            
            print(f"✓ Created test site: {test_site.name}")
            print(f"  Site ID: {test_site.id}")
            print(f"  Public key: {test_site_key}")
            return True
            
    except Exception as e:
        print(f"✗ Failed to setup test site: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_http_request(message):
    """Send single HTTP request to /api/chat"""
    try:
        session_id = str(uuid.uuid4())
        
        payload = {
            'site_key': test_site_key,
            'message': message,
            'session_id': session_id,
            'page_url': 'http://localhost:5000/test'
        }
        
        response = requests.post(
            API_BASE_URL,
            json=payload,
            timeout=10
        )
        
        return response.status_code == 200, session_id
        
    except Exception as e:
        print(f"  ✗ Request failed: {e}")
        return False, None


def send_traffic():
    """Send 100 real HTTP requests"""
    print(f"\n✓ Sending {TOTAL_REQUESTS} real HTTP requests...")
    print("  Please wait (this takes 30-60 seconds)...\n")
    
    successful = 0
    failed = 0
    session_ids = set()
    
    for i in range(TOTAL_REQUESTS):
        # Rotate through test intents
        intent = TEST_INTENTS[i % len(TEST_INTENTS)]
        message = intent['message']
        
        success, session_id = send_http_request(message)
        
        if success:
            successful += 1
            if session_id:
                session_ids.add(session_id)
        else:
            failed += 1
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            percentage = ((i + 1) / TOTAL_REQUESTS) * 100
            print(f"  Progress: {i + 1}/{TOTAL_REQUESTS} ({percentage:.0f}%)", end='\r')
        
        # Small delay to avoid overwhelming server
        time.sleep(0.1)
    
    print(f"\n✓ HTTP traffic completed:")
    print(f"  Successful: {successful}/{TOTAL_REQUESTS}")
    print(f"  Failed: {failed}/{TOTAL_REQUESTS}")
    print(f"  Unique sessions: {len(session_ids)}")
    
    return successful


def query_metrics_table(successful_requests):
    """Query phase1_metrics table and return analytics"""
    print("\n" + "=" * 80)
    print("REAL HTTP TRAFFIC - METRICS VALIDATION")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Wait a moment for any pending commits
        time.sleep(1)
        
        # Query 1: Total rows
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics WHERE phase_version = '1.0.0'")
        total_rows = cursor.fetchone()[0]
        
        print(f"\n📊 TELEMETRY COUNTS:")
        print(f"  HTTP requests sent:          {successful_requests}")
        print(f"  Metrics rows inserted:       {total_rows}")
        
        if total_rows == 0:
            print("\n❌ CRITICAL: No metrics logged!")
            print("   The orchestrator is NOT calling Phase1Metrics.create_from_orchestrator()")
            print("   Check: services/message_orchestrator.py _finalize() method")
            conn.close()
            return None
        
        if total_rows != successful_requests:
            print(f"\n⚠️  MISMATCH: Expected {successful_requests}, got {total_rows}")
            print("   Possible causes:")
            print("   - Some requests failed silently")
            print("   - Metrics logging failed for some requests")
        
        # Query 2: Confidence band distribution
        cursor.execute("""
            SELECT confidence_band, COUNT(*) as count
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
            GROUP BY confidence_band
            ORDER BY count DESC
        """)
        
        bands = cursor.fetchall()
        print(f"\n📈 CONFIDENCE BAND DISTRIBUTION:")
        for band, count in bands:
            pct = (count / total_rows * 100) if total_rows > 0 else 0
            print(f"  {band:8s}: {count:4d} ({pct:5.1f}%)")
        
        # Query 3: Clarification triggered
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN clarification_triggered THEN 1 END) as triggered,
                COUNT(CASE WHEN clarification_confirmed THEN 1 END) as confirmed,
                COUNT(CASE WHEN clarification_denied THEN 1 END) as denied
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        total, triggered, confirmed, denied = cursor.fetchone()
        trigger_pct = (triggered / total * 100) if total > 0 else 0
        confirm_pct = (confirmed / triggered * 100) if triggered > 0 else 0
        
        print(f"\n🎯 CLARIFICATION LOGIC:")
        print(f"  Total messages:              {total}")
        print(f"  Clarification triggered:    {triggered} ({trigger_pct:5.1f}%)")
        print(f"  Clarification confirmed:    {confirmed} ({confirm_pct:5.1f}% of triggered)")
        print(f"  Clarification denied:       {denied}")
        
        # Query 4: LLM invocation
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN llm_called THEN 1 END) as llm_count,
                ROUND(AVG(CASE WHEN llm_called THEN llm_response_time_ms END), 2) as avg_llm_ms
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        total, llm_count, avg_llm_ms = cursor.fetchone()
        llm_pct = (llm_count / total * 100) if total > 0 else 0
        llm_reduction = ((total - llm_count) / total * 100) if total > 0 else 0
        
        print(f"\n⚡ LLM INVOCATION:")
        print(f"  Total messages:              {total}")
        print(f"  LLM called:                  {llm_count} ({llm_pct:5.1f}%)")
        print(f"  LLM avoided (reduction):    {total - llm_count} ({llm_reduction:5.1f}%)")
        print(f"  Avg LLM response time:       {avg_llm_ms if avg_llm_ms else 'N/A'} ms")
        
        # Query 5: Response times
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                ROUND(AVG(total_response_time_ms), 2) as avg_ms,
                MIN(total_response_time_ms) as min_ms,
                MAX(total_response_time_ms) as max_ms
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        total, avg_ms, min_ms, max_ms = cursor.fetchone()
        
        print(f"\n⏱️  RESPONSE TIME PERFORMANCE:")
        print(f"  Average response time:       {avg_ms} ms")
        print(f"  Min response time:           {min_ms} ms")
        print(f"  Max response time:           {max_ms} ms")
        
        # Query 6: Workflow interference
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN workflow_active THEN 1 END) as workflow_count
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        workflow_count = cursor.fetchone()[0]
        workflow_pct = (workflow_count / total * 100) if total > 0 else 0
        
        print(f"\n🔄 WORKFLOW CONTEXT:")
        print(f"  Workflow active messages:    {workflow_count} ({workflow_pct:5.1f}%)")
        
        conn.close()
        
        # Return the 5 key numbers
        return {
            'total_rows': total_rows,
            'requests_sent': successful_requests,
            'trigger_rate': f"{trigger_pct:.1f}%",
            'confirmation_rate': f"{confirm_pct:.1f}%" if triggered > 0 else "N/A",
            'llm_reduction': f"{llm_reduction:.1f}%",
            'avg_response_ms': f"{avg_ms}",
        }
        
    except Exception as e:
        print(f"✗ Query failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def validate_results(metrics):
    """Validate the metrics against expectations"""
    if not metrics:
        print("\n" + "=" * 80)
        print("❌ VALIDATION FAILED - No metrics collected")
        print("=" * 80)
        return False
    
    print("\n" + "=" * 80)
    print("VALIDATION ASSESSMENT")
    print("=" * 80)
    
    total_rows = metrics['total_rows']
    requests_sent = metrics['requests_sent']
    
    checks = []
    
    # Check 1: Metrics recorded
    if total_rows == requests_sent:
        checks.append("✅ Metric count matches request count (no loss)")
    elif total_rows >= requests_sent * 0.95:
        checks.append("⚠️  Metric count 95%+ of requests (acceptable)")
    else:
        checks.append(f"❌ Metric count {total_rows} << requests {requests_sent} (LOSS DETECTED)")
    
    # Check 2: Clarification logic
    trigger_str = metrics['trigger_rate'].rstrip('%')
    trigger_pct = float(trigger_str) if trigger_str != 'N/A' else 0
    
    if 5 <= trigger_pct <= 40:
        checks.append(f"✅ Trigger rate {metrics['trigger_rate']} in optimal range")
    else:
        checks.append(f"⚠️  Trigger rate {metrics['trigger_rate']} outside 5-40% range")
    
    # Check 3: Response time
    resp_ms = float(metrics['avg_response_ms'])
    if resp_ms < 500:
        checks.append(f"✅ Response time {resp_ms}ms acceptable")
    elif resp_ms < 1000:
        checks.append(f"⚠️  Response time {resp_ms}ms slightly elevated")
    else:
        checks.append(f"❌ Response time {resp_ms}ms too high")
    
    # Check 4: LLM reduction
    llm_str = metrics['llm_reduction'].rstrip('%')
    llm_pct = float(llm_str) if llm_str != 'N/A' else 0
    
    if llm_pct > 20:
        checks.append(f"✅ LLM reduction {metrics['llm_reduction']} shows value")
    else:
        checks.append(f"⚠️  LLM reduction {metrics['llm_reduction']} lower than expected")
    
    for check in checks:
        print(f"  {check}")
    
    all_good = all(c.startswith('✅') for c in checks)
    
    print("\n" + "=" * 80)
    if all_good:
        print("✅ PRODUCTION TELEMETRY VALIDATED")
        print("=" * 80)
        print("\nThe orchestrator is correctly:")
        print("  1. Logging metrics on every request")
        print("  2. Capturing clarification triggers")
        print("  3. Recording LLM invocations")
        print("  4. Maintaining reasonable response times")
        print("\nTelemetry is trustworthy. Phase 2 planning can proceed.")
    else:
        print("⚠️  TELEMETRY NEEDS INVESTIGATION")
        print("=" * 80)
        print("\nBefore Phase 2, investigate:")
        for check in checks:
            if not check.startswith('✅'):
                print(f"  • {check}")
    
    return all_good


def main():
    print("=" * 80)
    print("REAL HTTP TRAFFIC VALIDATION TEST")
    print("=" * 80)
    print(f"\nTest Configuration:")
    print(f"  Total requests: {TOTAL_REQUESTS}")
    print(f"  API endpoint: {API_BASE_URL}")
    print(f"  Database: {DB_PATH}")
    
    try:
        # Start app
        if not start_flask_app():
            print("\n❌ Cannot proceed without app running")
            return False
        
        # Setup test site
        if not setup_test_site():
            print("\n❌ Cannot proceed without test site")
            stop_flask_app()
            return False
        
        # Send traffic
        successful = send_traffic()
        
        if successful == 0:
            print("\n❌ No successful requests sent")
            stop_flask_app()
            return False
        
        # Query metrics
        metrics = query_metrics_table(successful)
        
        # Validate
        success = validate_results(metrics)
        
        return success
        
    finally:
        stop_flask_app()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
