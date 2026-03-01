"""
Migration script for Stage 2 features.
Adds new columns to the plans table that SQLite create_all() won't add to existing tables.
"""
import sys
import os

# Ensure the project root is on the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app import create_app
from database import db
from sqlalchemy import text, inspect

def migrate():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        existing_cols = [c['name'] for c in inspector.get_columns('plans')]
        print(f"Current Plan columns: {existing_cols}")

        # New columns to add
        migrations = [
            ('max_forms', 'INTEGER DEFAULT 3'),
            ('max_webhooks', 'INTEGER DEFAULT 2'),
            ('ai_enabled', 'BOOLEAN DEFAULT 0'),
            ('workflows_enabled', 'BOOLEAN DEFAULT 1'),
            ('forms_enabled', 'BOOLEAN DEFAULT 1'),
            ('analytics_enabled', 'BOOLEAN DEFAULT 0'),
            ('webhooks_enabled', 'BOOLEAN DEFAULT 0'),
            ('custom_branding', 'BOOLEAN DEFAULT 0'),
            ('priority_support', 'BOOLEAN DEFAULT 0'),
        ]

        added = 0
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                try:
                    db.session.execute(text(f'ALTER TABLE plans ADD COLUMN {col_name} {col_type}'))
                    print(f"  + Added column: {col_name} ({col_type})")
                    added += 1
                except Exception as e:
                    print(f"  ! Skipped {col_name}: {e}")
            else:
                print(f"  = Column exists: {col_name}")

        if added > 0:
            db.session.commit()
            print(f"\nMigration complete: {added} columns added.")
        else:
            print("\nNo migration needed - all columns already present.")

if __name__ == '__main__':
    migrate()
