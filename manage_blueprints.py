#!/usr/bin/env python3
"""
Intent Management System - Handles blueprint initialization and updates
Supports both template files and user-uploaded intents without conflicts
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = 'instance/chatbot.db'

# Default blueprints (fallback if no templates available)
DEFAULT_BLUEPRINTS = [
    ('GREETING', 'info', 'Hello! How can I help you today?', 0.6, ['hello', 'hi', 'hey', 'greetings']),
    ('HELP', 'info', 'I am here to help! What do you need assistance with?', 0.7, ['help', 'assist', 'support', 'can you help']),
    ('PRICING', 'info', 'For pricing information, please contact our sales team.', 0.8, ['price', 'cost', 'pricing', 'how much']),
    ('BUSINESS_HOURS', 'info', 'Our business hours are Monday to Friday, 9 AM to 6 PM EST.', 0.75, ['hours', 'open', 'closing', 'schedule']),
    ('CONTACT_INFO', 'info', 'You can reach us at support@company.com or call 1-800-555-0123', 0.75, ['contact', 'email', 'phone', 'reach']),
    ('GOODBYE', 'info', 'Goodbye! Feel free to reach out anytime. Have a great day!', 0.6, ['bye', 'goodbye', 'see you', 'farewell']),
]

def load_template_intents():
    """Load intents from template JSON files in intent_templates/"""
    template_dir = Path('intent_templates')
    intents = []
    
    if not template_dir.exists():
        print("(No intent_templates/ directory found, using defaults)")
        return [(name, itype, resp, conf, phrases, None) for name, itype, resp, conf, phrases in DEFAULT_BLUEPRINTS]
    
    json_files = list(template_dir.glob('*.json'))
    if not json_files:
        print("(No .json files in intent_templates/, using defaults)")
        return [(name, itype, resp, conf, phrases, None) for name, itype, resp, conf, phrases in DEFAULT_BLUEPRINTS]
    
    print(f"Loading intents from {len(json_files)} template files...")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                file_intents = data.get('intents', [])
                for intent in file_intents:
                    name = intent.get('name', '').strip()
                    intent_type = intent.get('type', 'info')
                    response = intent.get('response', '').strip()
                    phrases = intent.get('phrases', [])
                    threshold = float(intent.get('confidence_threshold', intent.get('confidence', 0.7)))
                    
                    if name and response and phrases:
                        intents.append((name, intent_type, response, threshold, [p.strip() for p in phrases if p.strip()], json_file.name))
                        print(f"  ✓ {json_file.name}: {name}")
        except Exception as e:
            print(f"  ✗ Error reading {json_file.name}: {e}")
    
    return intents if intents else [(name, itype, resp, conf, phrases, None) for name, itype, resp, conf, phrases in DEFAULT_BLUEPRINTS]

def init_blueprints(force_reload=False):
    """
    Initialize blueprint intents in database.
    - Loads from intent_templates/*.json files if they exist
    - Falls back to defaults if no templates found  
    - Updates existing blueprints if force_reload=True
    - Preserves client-specific intents (site_id > 0)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Load intents - prioritize template files
        intents = load_template_intents()
        
        created = 0
        updated = 0
        skipped = 0
        
        for intent_name, intent_type, response, threshold, phrases, template_file in intents:
            # Check if blueprint exists
            c.execute('SELECT id FROM intents WHERE site_id=0 AND intent_name=?', (intent_name,))
            result = c.fetchone()
            
            if result:
                intent_id = result[0]
                if force_reload:
                    # Update existing blueprint
                    c.execute('''
                        UPDATE intents 
                        SET intent_type=?, response=?, confidence_threshold=?, template_file=?
                        WHERE id=?
                    ''', (intent_type, response, threshold, template_file, intent_id))
                    
                    # Delete old phrases and add new ones
                    c.execute('DELETE FROM intent_phrases WHERE intent_id=?', (intent_id,))
                    for phrase in phrases:
                        c.execute('''
                            INSERT INTO intent_phrases (intent_id, phrase)
                            VALUES (?, ?)
                        ''', (intent_id, phrase))
                    updated += 1
                else:
                    skipped += 1
            else:
                # Create new blueprint
                c.execute('''
                    INSERT INTO intents (site_id, intent_name, intent_type, response, confidence_threshold, template_file, created_at)
                    VALUES (0, ?, ?, ?, ?, ?, datetime('now'))
                ''', (intent_name, intent_type, response, threshold, template_file))
                intent_id = c.lastrowid
                
                # Add phrases
                for phrase in phrases:
                    c.execute('''
                        INSERT INTO intent_phrases (intent_id, phrase)
                        VALUES (?, ?)
                    ''', (intent_id, phrase))
                
                created += 1
        
        conn.commit()
        
        # Summary
        c.execute('SELECT COUNT(*) FROM intents WHERE site_id=0')
        total = c.fetchone()[0]
        
        print(f"\n✓ Blueprint initialization complete:")
        print(f"  Created: {created} new blueprints")
        print(f"  Updated: {updated} existing blueprints")
        print(f"  Skipped: {skipped} unchanged")
        print(f"  Total blueprints: {total}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

if __name__ == '__main__':
    import sys
    # Check for --force flag to reload existing blueprints from updated template files
    force_reload = '--force' in sys.argv
    
    if force_reload:
        print("Force reload enabled - will update existing blueprints from template files")
    
    init_blueprints(force_reload=force_reload)
