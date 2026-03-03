#!/usr/bin/env python3
"""
PASS 1: REAL HTTP TRAFFIC VALIDATION

Actual request flow:
1. Start Flask server (DISABLE_EMBEDDINGS=true)
2. Send 20 real HTTP requests
3. Query database - measure metrics insertion
4. Analyze: llm_called distribution, confidence_band distribution
5. Monitor logs for telemetry errors

No simulation. No schema tests. Full request path.
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import requests
from datetime import datetime

# Force deterministic boot
os.environ['DISABLE_EMBEDDINGS'] = 'true'

def check_metrics_before():
    """Get baseline metrics count"""
    try:
        conn = sqlite3.connect('instance/chatbot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"ERROR: Cannot query baseline: {e}")
        return None

def start_flask_server():
    """Start Flask server in background"""
    print("[1] Starting Flask server...")
    proc = subprocess.Popen(
        [sys.executable, 'app.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd()
    )
    time.sleep(8)  # Give server more time to boot and listen
    return proc

def get_valid_site_key():
    """Get a valid site_key from database"""
    try:
        conn = sqlite3.connect('instance/chatbot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT public_key FROM sites LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0]
    except:
        pass
    return None

def send_http_requests(count=20):
    """Send real HTTP requests"""
    print(f"\n[2] Sending {count} HTTP POST requests...")
    
    # Get a valid site_key
    site_key = get_valid_site_key()
    if not site_key:
        print("  ERROR: No valid site found in database")
        return [], [], ["No valid site_key"]
    
    print(f"  Using site_key: {site_key}")
    
    base_url = 'http://localhost:5000/api/chat'
    results = []
    latencies = []
    errors = []
    
    for i in range(count):
        try:
            payload = {
                'message': f'Test message {i}: what is this?',
                'session_id': f'pass1-test-{i}',
                'site_key': site_key,
                'page_url': 'http://localhost/test'
            }
            
            start = time.time()
            response = requests.post(base_url, json=payload, timeout=10)
            elapsed = time.time() - start
            latencies.append(elapsed)
            
            status = response.status_code
            print(f"  [{i+1:2d}] Status {status} | Latency {elapsed:.3f}s")
            
            results.append({
                'request_num': i,
                'status': status,
                'latency': elapsed,
                'success': status in [200, 201]
            })
            
        except Exception as e:
            error_msg = str(e)[:50]
            print(f"  [{i+1:2d}] ERROR: {error_msg}")
            errors.append(error_msg)
            results.append({
                'request_num': i,
                'status': 0,
                'latency': None,
                'success': False,
                'error': error_msg
            })
    
    successful = sum(1 for r in results if r['success'])
    avg_latency = sum(l for l in latencies if l is not None) / len([l for l in latencies if l is not None]) if latencies else 0
    
    print(f"\n  Summary: {successful}/{count} successful")
    print(f"  Avg latency: {avg_latency:.3f}s")
    print(f"  Errors: {len(errors)}")
    
    return results, latencies, errors

def check_metrics_after():
    """Get metrics after requests"""
    try:
        conn = sqlite3.connect('instance/chatbot.db')
        cursor = conn.cursor()
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM phase1_metrics")
        count = cursor.fetchone()[0]
        
        # LLM distribution
        cursor.execute("""
            SELECT llm_called, COUNT(*) as cnt 
            FROM phase1_metrics 
            WHERE timestamp > datetime('now', '-5 minutes')
            GROUP BY llm_called
        """)
        llm_dist = dict(cursor.fetchall())
        
        # Confidence band distribution
        cursor.execute("""
            SELECT confidence_band, COUNT(*) as cnt 
            FROM phase1_metrics 
            WHERE timestamp > datetime('now', '-5 minutes')
            GROUP BY confidence_band
        """)
        conf_dist = dict(cursor.fetchall())
        
        conn.close()
        
        return count, llm_dist, conf_dist
    except Exception as e:
        print(f"ERROR: Cannot query after: {e}")
        return None, None, None

def check_error_logs():
    """Check for telemetry errors in logs - simplified check"""
    try:
        # Look for error log files
        log_file = 'app.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                content = f.read()
                if 'Phase1Metrics logging failed' in content or 'CRITICAL' in content:
                    return ['Found telemetry error in app.log']
    except:
        pass
    return []

def main():
    print("\n" + "="*70)
    print("PASS 1: REAL HTTP TRAFFIC VALIDATION")
    print("="*70)
    print(f"Start time: {datetime.now().isoformat()}\n")
    
    # Step 0: Baseline
    print("[0] Baseline metrics count...")
    baseline = check_metrics_before()
    if baseline is None:
        print("FAIL: Cannot access database")
        return 1
    print(f"  Baseline: {baseline} records\n")
    
    # Step 1: Start server
    proc = start_flask_server()
    time.sleep(2)
    
    try:
        # Step 2: Send requests
        request_results, latencies, http_errors = send_http_requests(20)
        
        # Step 3: Check metrics
        print("\n[3] Querying metrics insertion...")
        new_count, llm_dist, conf_dist = check_metrics_after()
        
        if new_count is None:
            print("FAIL: Cannot query metrics")
            return 1
        
        inserted = new_count - baseline
        print(f"  Baseline: {baseline}")
        print(f"  After: {new_count}")
        print(f"  Inserted: {inserted} new records")
        
        # Step 4: Distributions
        print("\n[4] Metrics distribution...")
        print(f"  LLM called:")
        for llm_flag, cnt in sorted(llm_dist.items(), key=lambda x: str(x[0])):
            status = "YES" if llm_flag else "NO" if llm_flag is not None else "NULL"
            print(f"    {status}: {cnt}")
        
        print(f"  Confidence bands:")
        for band, cnt in sorted(conf_dist.items()):
            print(f"    {band}: {cnt}")
        
        # Step 5: Error logs
        print("\n[5] Scanning logs for telemetry errors...")
        telemetry_errors = check_error_logs()
        if telemetry_errors:
            print(f"  FOUND {len(telemetry_errors)} telemetry errors:")
            for err in telemetry_errors[:5]:  # Show first 5
                print(f"    - {err}")
        else:
            print(f"  No telemetry errors detected")
        
        # Step 6: Validation
        print("\n[6] Validation...")
        validation_pass = True
        
        if inserted > 0:
            print(f"  ✓ Metrics inserted: {inserted} records")
        else:
            print(f"  ✗ No metrics inserted")
            validation_pass = False
        
        successful_requests = sum(1 for r in request_results if r['success'])
        if successful_requests >= 15:  # At least 75% success
            print(f"  ✓ Request success rate: {successful_requests}/20 ({100*successful_requests//20}%)")
        else:
            print(f"  ✗ Request success rate too low: {successful_requests}/20")
            validation_pass = False
        
        if not telemetry_errors:
            print(f"  ✓ No telemetry errors in logs")
        else:
            print(f"  ✗ Telemetry errors detected")
            validation_pass = False
        
        if validation_pass:
            print(f"\n  RESULT: PASS 1 PASSED")
            return 0
        else:
            print(f"\n  RESULT: PASS 1 FAILED")
            return 1
            
    finally:
        # Cleanup
        print("\n[7] Cleanup...")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
        print("  Server stopped")

if __name__ == '__main__':
    sys.exit(main())
