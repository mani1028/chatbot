# Script to ensure every site has a default greeting intent

import sys
from pathlib import Path
import os
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from database import db
from models import Site, Intent, IntentPhrase

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'intent_templates', 'greetings_intents.json')

def import_greetings_for_site(site, greetings):
    imported = 0
    for intent_data in greetings:
        name = intent_data.get('name')
        if not name:
            print(f"Skipping intent with missing name for site_id={site.id}")
            continue
        response = intent_data.get('response')
        itype = intent_data.get('type', 'info')
        threshold = intent_data.get('confidence_threshold', 0.6)
        phrases = intent_data.get('phrases', [])
        # Check if intent exists for site
        existing = Intent.query.filter_by(site_id=site.id, intent_name=name).first()
        if existing:
            continue
        intent = Intent(site_id=site.id, intent_name=name, intent_type=itype, response=response, confidence_threshold=threshold)
        db.session.add(intent)
        db.session.flush()
        for p in phrases:
            db.session.add(IntentPhrase(intent_id=intent.id, phrase=p))
        imported += 1
    return imported

with app.app_context():
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        payload = json.load(f)
        greetings = payload.get('intents', [])
    total = 0
    for site in Site.query.all():
        total += import_greetings_for_site(site, greetings)
    db.session.commit()

print(f"Imported {total} greeting intents from template for all sites.")
