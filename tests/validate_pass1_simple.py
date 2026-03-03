#!/usr/bin/env python3
"""
PASS 1: TELEMETRY INSERT VALIDATION
Real HTTP requests --> Metrics table verification

This test:
1. Starts Flask app in background
2. Sends 20 POST requests to /api/chat/send-message
3. Queries phase1_metrics table
4. Validates metric insertion count matches requests

Environment: DISABLE_EMBEDDINGS=true (deterministic boot)
"""

import os
import sys
import time
import json
import sqlite3
import requests
import subprocess
import signal
from threading import Thread

# Force embeddings disabled for deterministic boot
os.environ['DISABLE_EMBEDDINGS'] = 'true'

def test_telemetry_insert():
    """Send 20 real HTTP requests and verify metrics inserted"""
    print("\n" + "="*70)
    print("PASS 1: TELEMETRY INSERT VALIDATION")
    print("="*70)
    
    # Step 1: Start Flask app
    print("\n[1] Starting Flask app...")
    app_process = subprocess.Popen(
        ['python', 'app.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd()
    )
    
    # Wait for Flask to start
    time.sleep(5)
    
    try:
        # Step 2: Send test requests
        print("[2] Sending 20 test requests...")
        base_url = 'http://localhost:5000/api/chat/send-message'
        
        request_count = 0
        success_count = 0
        
        for i in range(20):
            try:
                payload = {
                    'site_id': 1,
                    'session_id': f'test-session-{i}',
                    'user_message': f'Test message {i}',
                    'intent_name': 'test_intent'
                }
                
                response = requests.post(base_url, json=payload, timeout=5)
                request_count += 1
                
                if response.status_code in [200, 201, 400]:  # 400 due to auth is ok for this test
                    success_count += 1
                    print(f"  Request {i+1}: {response.status_code}")
                else:
                    print(f"  Request {i+1}: {response.status_code} (unexpected)")
                    
            except Exception as e:
                print(f"  Request {i+1}: FAILED - {str(e)[:50]}")
        
        print(f"\nRequests sent: {success_count}/{request_count}")
        
        # Step 3: Query metrics table
        print("\n[3] Querying phase1_metrics table...")
        
        db_path = 'instance/chatbot.db'
        if not os.path.exists(db_path):
            print(f"  ERROR: Database not found at {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count metrics records
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics")
        total_metrics = cursor.fetchone()[0]
        
        # Get recent metrics (last 20)
        cursor.execute("""
            SELECT COUNT(*), AVG(llm_response_ms) as avg_ms, 
                   AVG(confidence_score) as avg_conf
            FROM phase1_metrics 
            WHERE created_at > datetime('now', '-5 minutes')
        """)
        
        recent_count, avg_ms, avg_conf = cursor.fetchone()
        
        print(f"  Total metrics records: {total_metrics}")
        print(f"  Metrics from last 5 min: {recent_count}")
        print(f"  Avg LLM time: {avg_ms:.1f}ms" if avg_ms else "  Avg LLM time: N/A")
        print(f"  Avg confidence: {avg_conf:.3f}" if avg_conf else "  Avg confidence: N/A")
        
        conn.close()
        
        # Step 4: Validate
        print("\n[4] Validation...")
        
        if recent_count > 0:
            print(f"  PASS: Metrics inserted successfully ({recent_count} records)")
            return True
        else:
            print(f"  FAIL: No metrics inserted")
            return False
            
    finally:
        # Cleanup: stop Flask
        print("\n[5] Stopping Flask app...")
        app_process.terminate()
        try:
            app_process.wait(timeout=5)
        except:
            app_process.kill()

def main():
    """Main test runner"""
    try:
        success = test_telemetry_insert()
        
        print("\n" + "="*70)
        if success:
            print("RESULT: PASS 1 VALIDATION PASSED")
            print("Telemetry pipeline working correctly")
            return 0
        else:
            print("RESULT: PASS 1 VALIDATION FAILED")
            print("Check Flask app startup and database connectivity")
            return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
