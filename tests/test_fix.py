import requests
import json
import time

print("\n" + "="*70)
print("ARCHITECTURAL FIX VALIDATION TEST SUITE")
print("="*70)

API_URL = "http://localhost:5000/api/chat"

# Test cases for different intent types
tests = [
    {
        "name": "Test 1: Known Intent (Greeting)",
        "payload": {
            "site_key": "kernel_test_key",
            "message": "Hello there",
            "session_id": "test_greet"
        }
    },
    {
        "name": "Test 2: Unknown Intent (triggers LLM)",
        "payload": {
            "site_key": "kernel_test_key",
            "message": "Lorem ipsum dolor sit amet",
            "session_id": "test_unknown"
        }
    },
    {
        "name": "Test 3: Task Request",
        "payload": {
            "site_key": "kernel_test_key",
            "message": "create a new task for me",
            "session_id": "test_task"
        }
    }
]

overall_pass = True

for test in tests:
    print(f"\n\n{test['name']}")
    print("-" * 70)
    try:
        start = time.time()
        response = requests.post(API_URL, json=test['payload'])
        elapsed = time.time() - start
        print(f"Status: {response.status_code}")
        print(f"Response Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Intent: {data.get('intent')}")
            print(f"Confidence: {data.get('confidence')}")
            print(f"Response: {data.get('reply')[:80]}...")
            print("✓ PASS")
        else:
            print(f"✗ FAIL - Status {response.status_code}")
            print(f"Response: {response.text[:150]}")
            overall_pass = False
    except Exception as e:
        print(f"✗ FAIL - Exception: {e}")
        overall_pass = False

print("\n" + "="*70)
if overall_pass:
    print("✓ ALL TESTS PASSED - ARCHITECTURAL FIX VALIDATED")
else:
    print("✗ SOME TESTS FAILED - REVIEW NEEDED")
print("="*70)
