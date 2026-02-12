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
        print('Usage: python scripts/import_intents.py <json-file> [--client <client_id>]')
        sys.exit(1)

    json_path = Path(sys.argv[1])
    client_id = 1
    if '--client' in sys.argv:
        try:
            client_id = int(sys.argv[sys.argv.index('--client') + 1])
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

    sector = payload.get('sector')
    intents = payload.get('intents', [])

    if not intents:
        print('No intents found in file')
        sys.exit(1)

    with app.app_context():
        for it in intents:
            name = it.get('name')
            itype = it.get('type', 'info')
            response = it.get('response')
            threshold = it.get('confidence_threshold') or it.get('confidence', 0.7)
            phrases = it.get('phrases', [])
            workflow = it.get('workflow')
            config_required = it.get('config_required', [])

            if not name:
                print('Skipping intent with no name')
                continue

            # Check if intent exists for site (site_id 1) else create. Use site_id=1 for client import.
            site_id = client_id
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

            # Client config keys (create empty entries if missing)
            for key in config_required:
                key = key.strip()
                if not key:
                    continue
                exists_cfg = ClientConfig.query.filter_by(client_id=client_id, key=key).first()
                if not exists_cfg:
                    db.session.add(ClientConfig(client_id=client_id, key=key, value=''))
                    print(f'  + client_config key: {key} (empty)')

        try:
            db.session.commit()
            print('Import complete')
        except Exception as e:
            print('Import failed:', e)
            db.session.rollback()
