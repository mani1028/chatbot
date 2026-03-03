#!/usr/bin/env python3
"""Quick test of 6 scenarios - shorter timeout"""
import requests
import json

BASE_URL = "http://localhost:5000/api/chat"
SITE_KEY = "kernel_test_key"

p = 0
scenarios = [
    ("S1: Hours", "What are your hours", "s1"),
    ("S2: Book", "I want to book an appointment", "s2"),
    ("S3: Pricing", "I want pricing", "s3"),
]

print("\nRUNNING 3 QUICK TESTS\n")

for label, message, sid in scenarios:
    payload = {"site_key": SITE_KEY, "message": message, "session_id": sid}
    
    try:
        resp = requests.post(BASE_URL, json=payload, timeout=5)
        data = resp.json()
        intent = data.get("intent", "?")
        conf = data.get("confidence", 0)
        print(f"{label:15} | Intent: {intent:20} | Conf: {conf:.2f}")
    except Exception as e:
        print(f"{label:15} | ERROR: {str(e)[:40]}")

print()
