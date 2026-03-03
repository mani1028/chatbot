# AUTOMATED LEAD CAPTURE INTENT CREATION
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from models.intent import Intent, IntentPhrase
    from database import db
    from config import CONFIDENCE_THRESHOLD
    from flask import session
    from app import app
    with app.app_context():
        # Get current site_id (default to 1 if not set)
        site_id = 1
        # Check if already exists
        existing = Intent.query.filter_by(site_id=site_id, intent_name="capture_lead").first()
        if not existing:
            intent = Intent(
                site_id=site_id,
                intent_name="capture_lead",
                intent_type="LEAD",
                response="I'd be happy to help! Please provide your details below:"
            )
            db.session.add(intent)
            db.session.commit()
            phrases = ["speak to sales", "contact sales", "book appointment", "get a quote"]
            for phrase in phrases:
                db.session.add(IntentPhrase(intent_id=intent.id, phrase=phrase))
            db.session.commit()
            print("capture_lead intent created!")
        else:
            print("capture_lead intent already exists for this site.")
"""Import intents from a JSON file into the database.

Usage:
    python scripts/import_intents.py intent_templates/hospital_intents.json --client 1

The JSON format expected:
{
  "sector": "hospital",
  "intents": [ ... ]
}

Each intent:
  name, type (action|info|LEAD|HUMAN), response (template), confidence_threshold, phrases[], workflow, config_required[]

This script will create/lookup intents by (site_id, intent_name) and insert phrases, workflows and client_config keys (empty value).
"""
import sys
import json
from pathlib import Path

if __name__ == '__main__':


    if len(sys.argv) < 2:
        print('Usage: python scripts/import_intents.py <json-file> [--site <site_id>]')
        sys.exit(1)

    json_path = Path(sys.argv[1])
    site_id = 1
    if '--site' in sys.argv:
        try:
            site_id = int(sys.argv[sys.argv.index('--site') + 1])
        except Exception:
            pass

    if not json_path.exists():
        print('File not found:', json_path)
        sys.exit(1)

    # import project path and database
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import app
    from database import db
    from models import Intent, IntentPhrase, Workflow, ClientConfig

    with open(json_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    sector = payload.get('sector', 'global')
    intents = payload.get('intents', [])

    if not intents:
        print('No intents found in file')
        sys.exit(1)

    with app.app_context():

        for it in intents:
            name = it.get('name') or it.get('intent_name')
            itype = it.get('type', 'info')
            response = it.get('response')
            threshold = it.get('confidence_threshold') or it.get('confidence', CONFIDENCE_THRESHOLD)
            phrases = it.get('phrases', [])
            workflow = it.get('workflow')
            config_required = it.get('config_required', [])

            if not name:
                print('Skipping intent with no name')
                continue

            # Check if intent exists for site else create.
            existing = Intent.query.filter_by(site_id=site_id, intent_name=name).first()
            if existing:
                intent = existing
                print(f'Updating existing intent: {name} (site {site_id})')
                intent.intent_type = itype
                intent.response = response
                intent.sector = sector
                intent.confidence_threshold = threshold
            else:
                intent = Intent(site_id=site_id, intent_name=name, intent_type=itype, response=response, sector=sector, confidence_threshold=threshold)
                db.session.add(intent)
                db.session.flush()  # get id
                print(f'Created intent: {name} (site {site_id})')

            # Phrases: remove duplicates then add
            for p in phrases:
                p = (p or '').strip()
                if not p:
                    continue
                exists_p = IntentPhrase.query.filter_by(intent_id=intent.id, phrase=p).first()
                if not exists_p:
                    db.session.add(IntentPhrase(intent_id=intent.id, phrase=p))
                    print(f'  + phrase: {p}')

            # Workflow mapping
            if workflow:
                exists_wf = Workflow.query.filter_by(intent_id=intent.id, function_name=workflow).first()
                if not exists_wf:
                    db.session.add(Workflow(intent_id=intent.id, function_name=workflow))
                    print(f'  + workflow: {workflow}')

            # Site config keys (create empty entries if missing)
            for key in config_required:
                key = key.strip()
                if not key:
                    continue
                exists_cfg = ClientConfig.query.filter_by(site_id=site_id, key=key).first()
                if not exists_cfg:
                    db.session.add(ClientConfig(site_id=site_id, key=key, value=''))
                    print(f'  + site_config key: {key} (empty)')

        try:
            db.session.commit()
            print('Import complete')
        except Exception as e:
            print('Import failed:', e)
            db.session.rollback()
