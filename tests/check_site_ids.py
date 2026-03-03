"""
Check what site_ids exist in the intents table
"""

from app import app
from database import db
from models.intent import Intent

with app.app_context():
    print("[CHECK] All intents and their site_ids:", flush=True)
    print("=" * 70, flush=True)
    
    intents = Intent.query.all()
    
    site_ids = set()
    for intent in intents:
        site_ids.add(intent.site_id)
        if intent.id in [9, 1, 2]:  # Show specific intents
            print(f"  - ID {intent.id}: {intent.intent_name} (site_id: {intent.site_id})", flush=True)
    
    print(f"\nUnique site_ids: {sorted(site_ids)}", flush=True)
    
    print("\n[CHECK] Counting intents by site_id:", flush=True)
    for site_id in sorted(site_ids):
        count = Intent.query.filter(Intent.site_id == site_id).count()
        print(f"  - site_id {site_id}: {count} intents", flush=True)
