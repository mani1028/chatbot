#!/usr/bin/env python
"""Direct test of auto-suggestion-metrics endpoint logic"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.phase1_metrics import Phase1Metrics
from models.unknown_intent_log import UnknownIntentLog
from models.admin import Admin
from database import db
from datetime import datetime, timedelta

with app.app_context():
    print("\n" + "="*60)
    print("TESTING AUTO-SUGGESTION-METRICS LOGIC")
    print("="*60)
    
    try:
        # Create test admin
        test_admin = Admin.query.filter_by(username='admin').first()
        if not test_admin:
            print("❌ No admin found")
            sys.exit(1)
        
        print(f"✓ Using admin: {test_admin.username}")
        
        # Simulate the endpoint logic
        site_id = None
        now = datetime.utcnow()
        start_date = now - timedelta(days=7)
        
        print(f"✓ Query date range: {start_date} to {now}")
        
        # Get unknown intents
        unknown_logs = UnknownIntentLog.query.filter(
            UnknownIntentLog.created_at >= start_date
        )
        
        if site_id:
            unknown_logs = unknown_logs.filter(UnknownIntentLog.site_id == site_id)
        
        unknown_logs = unknown_logs.all()
        print(f"✓ Found {len(unknown_logs)} unknown logs")
        
        # Count phrases
        phrase_counts = {}
        for log in unknown_logs:
            try:
                phrase = (log.message or '').lower().strip()
                if phrase:
                    phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
            except Exception as e:
                print(f"❌ Error processing log {log.id}: {e}")
                continue
        
        print(f"✓ Found {len(phrase_counts)} unique phrases")
        
        # Find high-frequency phrases
        high_frequency = [
            {"phrase": p, "count": c, "potential_savings": round(c * 0.0006, 4)}
            for p, c in phrase_counts.items() if c >= 2
        ]
        
        high_frequency.sort(key=lambda x: x['count'], reverse=True)
        print(f"✓ Found {len(high_frequency)} high-frequency phrases")
        
        # Calculate metrics
        total_unknown = len(unknown_logs)
        auto_suggestible = len(high_frequency)
        learning_efficiency = round((auto_suggestible / total_unknown * 100), 2) if total_unknown else 0
        
        # Calculate savings
        savings_sum = sum(p['potential_savings'] for p in high_frequency)
        print(f"✓ Total potential savings: ${savings_sum}")
        
        # Build response
        response = {
            "site_id": site_id,
            "total_unknown": total_unknown,
            "auto_suggestible_phrases": len(high_frequency),
            "learning_efficiency": learning_efficiency,
            "top_phrases": high_frequency[:10],
            "potential_daily_savings": round(savings_sum, 4)
        }
        
        print(f"\n✅ PASS - Response would be:")
        import json
        print(json.dumps(response, indent=2))
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
