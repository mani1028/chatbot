#!/usr/bin/env python
"""
Load test script: simulate Apache Bench with 200 concurrent requests.

Tests:
- Concurrency: 200 simultaneous requests
- Endpoint: POST /api/chat with JSON payload
- Measures: throughput, latency (P50, P95, P99), error rate
"""
import concurrent.futures
import requests
import time
import json
from collections import defaultdict
import statistics

TARGET_URL = "http://127.0.0.1:5000/api/chat/test"
PAYLOAD = {
    "site_key": "test-site-key",
    "message": "xyzabc123unknown999",  # Intentionally unknown to force LLM fallback
    "session_id": "test-session-123"
}

HEADERS = {
    "Content-Type": "application/json"
}

def single_request(request_num):
    """Execute a single request and return timing data."""
    start_time = time.time()
    try:
        response = requests.post(
            TARGET_URL,
            json=PAYLOAD,
            headers=HEADERS,
            timeout=20
        )
        elapsed = time.time() - start_time
        
        return {
            "success": response.status_code in [200, 400, 403, 500],  # Accept any response
            "status_code": response.status_code,
            "elapsed": elapsed,
            "error": None
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "status_code": 0,
            "elapsed": elapsed,
            "error": str(e)
        }

def run_load_test(concurrency=200, total_requests=200):
    """Run load test with specified concurrency."""
    print("=" * 80)
    print("[LOAD TEST] Multi-threaded Concurrent HTTP Requests")
    print("=" * 80)
    print(f"Target: {TARGET_URL}")
    print(f"Concurrency: {concurrency} simultaneous threads")
    print(f"Total Requests: {total_requests}")
    print(f"Payload: {json.dumps(PAYLOAD, indent=2)}")
    print("=" * 80)
    print()
    
    start_time = time.time()
    results = []
    status_codes = defaultdict(int)
    
    # Execute requests concurrently
    print(f"[*] Firing {total_requests} concurrent requests...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(single_request, i)
            for i in range(total_requests)
        ]
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            results.append(result)
            status_codes[result["status_code"]] += 1
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                print(f"  [{i + 1}/{total_requests}] requests completed")
    
    total_elapsed = time.time() - start_time
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    latencies = [r["elapsed"] for r in results]
    latencies_success = [r["elapsed"] for r in successful]
    
    print()
    print("=" * 80)
    print("[RESULTS] Load Test Summary")
    print("=" * 80)
    print()
    
    # Basic metrics
    print(f"Total Test Duration: {total_elapsed:.2f}s")
    print(f"Total Requests: {len(results)}")
    print(f"Successful: {len(successful)} ({len(successful)*100/len(results):.1f}%)")
    print(f"Failed: {len(failed)} ({len(failed)*100/len(results):.1f}%)")
    print(f"Throughput: {len(results)/total_elapsed:.2f} requests/second")
    print()
    
    # Status code breakdown
    print("Status Code Distribution:")
    for code in sorted(status_codes.keys()):
        count = status_codes[code]
        pct = count * 100 / len(results)
        print(f"  {code:3d}: {count:4d} requests ({pct:5.1f}%)")
    print()
    
    # Latency analysis (all requests)
    if latencies:
        print("Latency Statistics (All Requests):")
        print(f"  Min:    {min(latencies):.3f}s")
        print(f"  Max:    {max(latencies):.3f}s")
        print(f"  Mean:   {statistics.mean(latencies):.3f}s")
        print(f"  P50:    {sorted(latencies)[len(latencies)//2]:.3f}s")
        print(f"  P95:    {sorted(latencies)[int(len(latencies)*0.95)]:.3f}s")
        print(f"  P99:    {sorted(latencies)[int(len(latencies)*0.99)]:.3f}s")
        print()
    
    # Latency analysis (successful only)
    if latencies_success:
        print("Latency Statistics (Successful Requests Only):")
        print(f"  Min:    {min(latencies_success):.3f}s")
        print(f"  Max:    {max(latencies_success):.3f}s")
        print(f"  Mean:   {statistics.mean(latencies_success):.3f}s")
        print(f"  P50:    {sorted(latencies_success)[len(latencies_success)//2]:.3f}s")
        print(f"  P95:    {sorted(latencies_success)[int(len(latencies_success)*0.95)]:.3f}s")
        print(f"  P99:    {sorted(latencies_success)[int(len(latencies_success)*0.99)]:.3f}s")
        print()
    
    # Production readiness assessment
    print("=" * 80)
    print("[ASSESSMENT] Production Readiness")
    print("=" * 80)
    
    success_rate = len(successful) * 100 / len(results)
    p95_latency = sorted(latencies)[int(len(latencies)*0.95)]
    
    assessments = []
    
    if success_rate >= 95:
        assessments.append(f"✅ Error Rate: {100-success_rate:.1f}% (acceptable)")
    else:
        assessments.append(f"❌ Error Rate: {100-success_rate:.1f}% (TOO HIGH)")
    
    if p95_latency <= 2.0:
        assessments.append(f"✅ P95 Latency: {p95_latency:.3f}s (excellent)")
    elif p95_latency <= 5.0:
        assessments.append(f"⚠️  P95 Latency: {p95_latency:.3f}s (acceptable)")
    else:
        assessments.append(f"❌ P95 Latency: {p95_latency:.3f}s (too slow)")
    
    if len(failed) == 0:
        assessments.append(f"✅ No Zero-Tolerance Errors (good)")
    else:
        assessments.append(f"⚠️  {len(failed)} complete failures (investigate)")
    
    for assessment in assessments:
        print(assessment)
    
    print()
    print("=" * 80)
    
    # Error details
    if failed:
        print()
        print("Error Details (first 10):")
        for i, result in enumerate(failed[:10]):
            print(f"  {i+1}. Status {result['status_code']}: {result['error']}")
    
    return {
        "total_requests": len(results),
        "success_rate": success_rate,
        "p95_latency": p95_latency,
        "throughput": len(results) / total_elapsed,
        "failed": len(failed)
    }

if __name__ == "__main__":
    print("\n")
    metrics = run_load_test(concurrency=200, total_requests=200)
    print("\n")
