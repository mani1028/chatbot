"""
Migration Script - Seed Intents from JSON files
This script loads intent definitions from JSON files and populates the database
Run once during initial setup or when updating intent definitions
"""

import json
import os
from app import app, db
from models import Intent

INTENTS_DIR = os.path.join(os.path.dirname(__file__), 'intents')

def load_intents_from_files():
    """Load all intents from JSON files in the intents/ directory"""
    all_intents = []
    
    if not os.path.exists(INTENTS_DIR):
        print(f"Error: {INTENTS_DIR} directory not found")
        return all_intents
    
    # Load all JSON files in intents directory
    for filename in os.listdir(INTENTS_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(INTENTS_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'intents' in data:
                        all_intents.extend(data['intents'])
                        print(f"✓ Loaded {len(data['intents'])} intents from {filename}")
            except Exception as e:
                print(f"✗ Error loading {filename}: {str(e)}")
    
    return all_intents

def seed_database():
    """Seed the database with intents from JSON files"""
    with app.app_context():
        # Get existing intents to avoid duplicates
        existing_intents = {intent.intent_name for intent in Intent.query.all()}
        
        # Load intents from files
        intents_data = load_intents_from_files()
        
        if not intents_data:
            print("No intents found to load")
            return
        
        # Add new intents to database
        added = 0
        skipped = 0
        
        for intent_data in intents_data:
            intent_name = intent_data.get('intent_name')
            
            if intent_name in existing_intents:
                print(f"⊘ Skipped (already exists): {intent_name}")
                skipped += 1
                continue
            
            try:
                intent = Intent(
                    intent_name=intent_name,
                    category=intent_data.get('category', 'General'),
                    short_response=intent_data.get('short_response', ''),
                    detailed_response=intent_data.get('detailed_response', ''),
                    requires_handoff=intent_data.get('requires_handoff', False)
                )
                intent.set_training_phrases(intent_data.get('training_phrases', []))
                
                db.session.add(intent)
                added += 1
                print(f"✓ Added: {intent_name}")
            
            except Exception as e:
                print(f"✗ Error adding {intent_name}: {str(e)}")
                skipped += 1
        
        # Commit all changes
        try:
            db.session.commit()
            print(f"\n✓ Successfully seeded database")
            print(f"  - Added: {added} new intents")
            print(f"  - Skipped: {skipped} existing/error intents")
            print(f"  - Total intents in database: {Intent.query.count()}")
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error committing to database: {str(e)}")

if __name__ == '__main__':
    print("=" * 50)
    print("Intent Database Seeding Script")
    print("=" * 50)
    seed_database()
    print("=" * 50)
