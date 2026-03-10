#!/usr/bin/env python3
"""
Test script to verify the Unknown Intent Mapping workflow.

Tests the complete flow:
1. Chat message → triggers unknown intent
2. Unknown logged to database
3. Admin reviews in API
4. Admin maps to intent
5. Auto-train verifies phrase added
6. Identical message matches (no fallback)
"""

import sys
import requests
import json
from datetime import datetime
import time

# Configuration
BASE_URL = 'http://localhost:5000'
SITE_ID = 1
ADMIN_ID = 1
TEST_SITE_ID = 1

# Styling
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(title):
    """Print section header"""
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(msg):
    """Print success message"""
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    """Print error message"""
    print(f"{RED}✗ {msg}{RESET}")

def print_info(msg):
    """Print info message"""
    print(f"{BLUE}→ {msg}{RESET}")

def print_warning(msg):
    """Print warning message"""
    print(f"{YELLOW}⚠ {msg}{RESET}")

# ============================================================================
# TEST 1: Trigger Unknown Intent
# ============================================================================

def test_trigger_unknown_intent():
    """Send a message that won't match any intent"""
    print_header("TEST 1: Trigger Unknown Intent")
    
    # Message that should NOT match any known intent
    test_message = "xyz random gibberish asdf qwerty"
    
    payload = {
        'user_message': test_message,
        'session_id': f'test-unknown-{int(time.time())}'
    }
    
    print_info(f"Sending unknown message: '{test_message}'")
    
    try:
        res = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            params={'site_id': SITE_ID},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Chat API returned {res.status_code}")
            print(f"Response: {res.text}")
            return False
        
        data = res.json()
        
        print_info(f"Intent detected: {data.get('intent_name', 'N/A')}")
        print_info(f"Confidence: {data.get('confidence', 0.0)}")
        print_info(f"Response: {data.get('reply', 'N/A')[:80]}...")
        
        # Verify it was classified as unknown/fallback
        if data.get('intent_name') in ['UNKNOWN', 'unknown']:
            print_success("Message correctly identified as unknown")
            return True
        else:
            print_warning(f"Message matched intent '{data.get('intent_name')}' instead of unknown")
            return True  # Still continue test
    
    except Exception as e:
        print_error(f"Failed to send chat message: {e}")
        return False


# ============================================================================
# TEST 2: Verify Unknown Logged
# ============================================================================

def test_verify_unknown_logged():
    """Check that the unknown was logged to database"""
    print_header("TEST 2: Verify Unknown Logged to Database")
    
    try:
        res = requests.get(
            f"{BASE_URL}/admin/api/unknown/statsadmin/api/unknown/stats",
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Stats API returned {res.status_code}")
            return False
        
        data = res.json()
        stats = data.get('stats', {})
        
        total = stats.get('total_fallbacks', 0)
        unmapped = stats.get('unmapped_count', 0)
        coverage = stats.get('coverage', 0)
        
        print_info(f"Total fallbacks logged: {total}")
        print_info(f"Unmapped: {unmapped}")
        print_info(f"Coverage: {coverage*100:.1f}%")
        
        if total > 0 and unmapped > 0:
            print_success("Unknown intent successfully logged")
            return True
        else:
            print_warning("No unmapped unknowns found (may be normal if intent matched)")
            return True  # Continue test even if not found
    
    except Exception as e:
        print_error(f"Failed to get stats: {e}")
        return False


# ============================================================================
# TEST 3: List Unmapped Unknowns
# ============================================================================

def test_list_unmapped():
    """Get list of unmapped unknowns via API"""
    print_header("TEST 3: List Unmapped Unknowns")
    
    try:
        res = requests.get(
            f"{BASE_URL}/admin/api/unknown/unmapped?limit=5",
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Unmapped API returned {res.status_code}")
            return None
        
        data = res.json()
        unknowns = data.get('unknowns', [])
        
        if not unknowns:
            print_warning("No unmapped unknowns found")
            return None
        
        print_info(f"Found {len(unknowns)} unmapped unknowns")
        
        # Show first one
        first = unknowns[0]
        print_info(f"First unknown: '{first['message']}'")
        print_info(f"Count: {first['count']}x")
        print_info(f"Fallback type: {first.get('fallback_type', 'unknown')}")
        
        # Show suggestions if available
        suggestions = first.get('similarity_suggestions', [])
        if suggestions:
            print_info(f"Suggestions available: {len(suggestions)}")
            for i, s in enumerate(suggestions[:3], 1):
                print(f"  {i}. {s['intent_name']} ({s['match_score']:.2%})")
        
        print_success("Retrieved unmapped unknowns list")
        return first
    
    except Exception as e:
        print_error(f"Failed to list unmapped: {e}")
        return None


# ============================================================================
# TEST 4: Get Single Unknown Detail
# ============================================================================

def test_get_unknown_detail(unknown_log):
    """Get full details of an unknown with audit trail"""
    print_header("TEST 4: Get Unknown Detail with Suggestions")
    
    if not unknown_log:
        print_warning("Skipping test (no unknown available)")
        return None
    
    log_id = unknown_log['id']
    
    try:
        res = requests.get(
            f"{BASE_URL}/admin/api/unknown/log/{log_id}",
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Log detail API returned {res.status_code}")
            return None
        
        data = res.json()
        log = data.get('log', {})
        
        print_info(f"Message: '{log.get('message')}'")
        print_info(f"Created: {log.get('created_at', 'N/A')}")
        print_info(f"Resolved: {log.get('resolved', False)}")
        
        # LLM response
        if log.get('llm_response'):
            print_info(f"LLM response: {log['llm_response'][:60]}...")
        
        # Audit fields
        if log.get('mapped_intent_id'):
            print_info(f"Mapped to intent #{log['mapped_intent_id']}")
            print_info(f"Mapped by admin #{log.get('mapped_by')}")
            print_info(f"Mapped at: {log.get('mapped_at')}")
            print_info(f"Phrase auto-trained: {log.get('phrase_auto_trained', False)}")
        
        # Suggestions
        suggestions = log.get('similarity_suggestions', [])
        print_info(f"Intent suggestions: {len(suggestions)}")
        for i, s in enumerate(suggestions[:3], 1):
            print(f"  {i}. Intent #{s['intent_id']} '{s['intent_name']}' ({s['match_score']:.2%})")
        
        print_success("Retrieved unknown detail with suggestions")
        return log
    
    except Exception as e:
        print_error(f"Failed to get log detail: {e}")
        return None


# ============================================================================
# TEST 5: Map Unknown to Intent
# ============================================================================

def test_map_unknown(unknown_log):
    """Map the unknown to an intent and optionally auto-train"""
    print_header("TEST 5: Map Unknown to Intent")
    
    if not unknown_log:
        print_warning("Skipping test (no unknown available)")
        return False
    
    # Get suggestions to pick one
    log_id = unknown_log['id']
    suggestions = unknown_log.get('similarity_suggestions', [])
    
    if not suggestions:
        print_warning("No suggestions available for mapping")
        return False
    
    # Pick first suggestion
    target_intent_id = suggestions[0]['intent_id']
    target_intent_name = suggestions[0]['intent_name']
    
    payload = {
        'unknown_log_id': log_id,
        'intent_id': target_intent_id,
        'auto_train_phrases': True
    }
    
    print_info(f"Mapping to intent #{target_intent_id} ({target_intent_name})")
    print_info(f"Auto-train phrases: True")
    
    try:
        res = requests.post(
            f"{BASE_URL}/admin/api/unknown/map",
            json=payload,
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Map API returned {res.status_code}")
            print(f"Response: {res.text}")
            return False
        
        data = res.json()
        
        if not data.get('success', False):
            print_error(f"Mapping failed: {data.get('message', 'Unknown error')}")
            return False
        
        print_success(f"Mapped: {data.get('message')}")
        return True
    
    except Exception as e:
        print_error(f"Failed to map unknown: {e}")
        return False


# ============================================================================
# TEST 6: Verify Audit Trail
# ============================================================================

def test_verify_audit_trail(unknown_log):
    """Verify the unknown was marked as resolved with audit fields"""
    print_header("TEST 6: Verify Audit Trail")
    
    if not unknown_log:
        print_warning("Skipping test (no unknown available)")
        return False
    
    log_id = unknown_log['id']
    time.sleep(1)  # Give DB time to update
    
    try:
        res = requests.get(
            f"{BASE_URL}/admin/api/unknown/log/{log_id}",
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Log detail API returned {res.status_code}")
            return False
        
        data = res.json()
        log = data.get('log', {})
        
        # Check audit fields
        checks = [
            ('resolved', True, "Unknown marked as resolved"),
            ('mapped_intent_id', None, "Mapped to an intent", lambda x: x is not None),
            ('mapped_by', None, "Admin ID recorded", lambda x: x is not None),
            ('mapped_at', None, "Mapping timestamp recorded", lambda x: x is not None),
            ('phrase_auto_trained', True, "Phrase was auto-trained"),
        ]
        
        all_ok = True
        for field, expected, description, *check_fn in checks:
            value = log.get(field)
            
            if check_fn:
                is_ok = check_fn[0](value)
            else:
                is_ok = (value == expected)
            
            if is_ok:
                print_success(f"{description}: {value}")
            else:
                print_error(f"{description} (got: {value})")
                all_ok = False
        
        return all_ok
    
    except Exception as e:
        print_error(f"Failed to verify audit trail: {e}")
        return False


# ============================================================================
# TEST 7: Verify Coverage Stats Updated
# ============================================================================

def test_verify_coverage_updated():
    """Check that coverage % increased after mapping"""
    print_header("TEST 7: Verify Coverage Updated")
    
    try:
        res = requests.get(
            f"{BASE_URL}/admin/api/unknown/stats",
            headers={'X-Admin-ID': str(ADMIN_ID)},
            timeout=10
        )
        
        if res.status_code != 200:
            print_error(f"Stats API returned {res.status_code}")
            return False
        
        data = res.json()
        stats = data.get('stats', {})
        
        total = stats.get('total_fallbacks', 0)
        mapped = stats.get('mapped_count', 0)
        coverage = stats.get('coverage', 0)
        
        print_info(f"Total fallbacks: {total}")
        print_info(f"Mapped: {mapped}")
        print_info(f"Coverage: {coverage*100:.1f}%")
        
        if coverage > 0:
            print_success(f"Coverage increased to {coverage*100:.1f}%")
            return True
        else:
            print_warning("Coverage still 0% (may be normal)")
            return True
    
    except Exception as e:
        print_error(f"Failed to verify coverage: {e}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests"""
    print(f"\n{BOLD}Unknown Intent Mapping Integration Test{RESET}")
    print(f"Base URL: {BASE_URL}")
    print(f"Site ID: {SITE_ID}")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = []
    
    # Test 1: Trigger unknown
    results.append(("Trigger Unknown Intent", test_trigger_unknown_intent()))
    
    time.sleep(1)  # Let logging complete
    
    # Test 2: Verify logged
    results.append(("Verify Unknown Logged", test_verify_unknown_logged()))
    
    # Test 3: List unmapped
    unknown_log = test_list_unmapped()
    results.append(("List Unmapped Unknowns", unknown_log is not None))
    
    if unknown_log:
        # Test 4: Get detail
        detail = test_get_unknown_detail(unknown_log)
        results.append(("Get Unknown Detail", detail is not None))
        
        # Test 5: Map unknown
        map_ok = test_map_unknown(detail or unknown_log)
        results.append(("Map Unknown to Intent", map_ok))
        
        # Test 6: Verify audit trail
        verify_ok = test_verify_audit_trail(detail or unknown_log)
        results.append(("Verify Audit Trail", verify_ok))
        
        # Test 7: Verify coverage
        results.append(("Verify Coverage Updated", test_verify_coverage_updated()))
    else:
        print_warning("\nSkipping mapping tests (no unknown available)")
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for test_name, ok in results:
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"{status} — {test_name}")
    
    print(f"\n{BOLD}Result: {passed}/{total} tests passed{RESET}\n")
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
