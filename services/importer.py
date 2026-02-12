import json
from database import db
from models import Intent, IntentPhrase, Workflow, ClientConfig

def import_sector_template(site_id, json_data):
    """
    Imports intents, phrases, and config from a JSON dictionary into the database for a specific site.
    """
    try:
        sector = json_data.get('sector')
        intents = json_data.get('intents', [])

        if not intents:
            return {"success": False, "message": "No intents found in JSON"}

        created_count = 0
        # Clear existing intents for this sector/site if needed? 
        # For now, we append/update.

        for it in intents:
            name = it.get('name')
            if not name:
                continue

            # 1. Create/Update Intent
            intent = Intent.query.filter_by(site_id=site_id, intent_name=name).first()
            if not intent:
                intent = Intent(
                    site_id=site_id, 
                    intent_name=name, 
                    intent_type=it.get('type', 'info'), 
                    response=it.get('response'), 
                    sector=sector, 
                    confidence_threshold=it.get('confidence_threshold', 0.7)
                )
                db.session.add(intent)
                db.session.flush() # Get ID
                created_count += 1
            else:
                # Update existing
                intent.response = it.get('response')
                intent.confidence_threshold = it.get('confidence_threshold', 0.7)

            # 2. Add Phrases
            existing_phrases = [p.phrase for p in intent.phrases]
            for p_text in it.get('phrases', []):
                p_text = p_text.strip()
                if p_text and p_text not in existing_phrases:
                    db.session.add(IntentPhrase(intent_id=intent.id, phrase=p_text))

            # 3. Add Workflow
            wf_name = it.get('workflow')
            if wf_name:
                existing_wf = Workflow.query.filter_by(intent_id=intent.id).first()
                if not existing_wf:
                    db.session.add(Workflow(intent_id=intent.id, function_name=wf_name))
                elif existing_wf.function_name != wf_name:
                    existing_wf.function_name = wf_name

            # 4. Register Config Keys
            for key in it.get('config_required', []):
                exists = ClientConfig.query.filter_by(client_id=site_id, key=key).first()
                if not exists:
                    db.session.add(ClientConfig(client_id=site_id, key=key, value=''))

        db.session.commit()
        return {"success": True, "message": f"Successfully processed {len(intents)} intents."}

    except Exception as e:
        db.session.rollback()
        return {"success": False, "message": str(e)}
