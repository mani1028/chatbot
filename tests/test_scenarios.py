#!/usr/bin/env python3
"""Quick test of 6 scenarios"""
import requests
import json
import time

BASE_URL = "http://localhost:5000/api/chat"
SITE_KEY = "kernel_test_key"

scenarios = [
    ("S1: Hours", "What are your hours", "scenario_1"),
    ("S2: Book", "I want to book an appointment", "scenario_2"),
    ("S3: Pricing", "I want pricing", "scenario_3"),
    ("S4: Human", "I need a human", "scenario_4"),
    ("S5: Nonsense", "asdlkfj aslkfj", "scenario_5"),
    ("S6a: Book", "I want to book", "scenario_6"),
]

print("\n" + "="*80)
print("RUNNING 6 TEST SCENARIOS")
print("="*80)

for label, message, session_id in scenarios:
    payload = {
        "site_key": SITE_KEY,
        "message": message,
        "session_id": session_id
    }
    
    try:
        resp = requests.post(BASE_URL, json=payload, timeout=10)
        data = resp.json()
        
        intent = data.get("intent", "?")
        conf = data.get("confidence", 0)
        reply = data.get("reply", "")[:40]
        
        print(f"{label:15} | Intent: {intent:15} | Conf: {conf:.2f} | Reply: {reply}...")
        
    except Exception as e:
        print(f"{label:15} | ERROR: {str(e)[:40]}")
    
    time.sleep(0.5)

print("="*80 + "\n")
