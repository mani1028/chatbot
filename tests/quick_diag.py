#!/usr/bin/env python3
"""Quick intent diagnostic via Flask context"""
import time
time.sleep(2)  # Let Flask start

from app import app
with app.app_context():
    from models.intent import Intent
    from models.site import Site
    
    site = Site.query.filter_by(site_key="kernel_test_key").first()
    if site:
        print(f"\n✓ Test site found: id={site.id}")
        
        bh = Intent.query.filter_by(intent_name="business_hours").first()
        if bh:
            print(f"✓ business_hours exists: site_id={bh.site_id}, phrases={len(bh.phrases or [])}")
            if bh.site_id == 0:
                print(f"  → GLOBAL (visible to all sites) ✓")
            elif bh.site_id == site.id:
                print(f"  → Site-scoped (only this site) ✓")
            else:
                print(f"  → Site-scoped (DIFFERENT site {bh.site_id}) ✗")
        else:
            print(f"✗ business_hours NOT found")
        
        print(f"\nAll accessible intents: {Intent.query.filter((Intent.site_id==0)|(Intent.site_id==site.id)).count()}")
    else:
        print("✗ Site not found")
