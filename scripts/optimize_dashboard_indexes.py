"""
Database Index Optimization Script
Adds indexes to frequently queried columns for dashboard performance.
Run this once to improve dashboard load times significantly.
"""
import os
import sys
# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import app, db

def add_dashboard_indexes():
    """Add indexes for dashboard queries."""
    with app.app_context():
        with db.engine.connect() as conn:
            # Determine database type
            db_url = str(db.engine.url)
            is_sqlite = 'sqlite' in db_url
            is_mysql = 'mysql' in db_url or 'MariaDB' in db_url
            is_postgres = 'postgresql' in db_url
            
            # SQLite-compatible index definitions (no DESC notation)
            if is_sqlite:
                indexes_to_create = [
                    ("chat_log", "site_id", "idx_chatlog_site"),
                    ("chat_log", "confidence", "idx_chatlog_conf"),
                    ("intent", "site_id", "idx_intent_site"),
                    ("lead_capture", "site_id", "idx_leads_site"),
                    ("contact_request", "site_id", "idx_contact_site"),
                ]
            else:
                # MySQL/PostgreSQL with DESC support
                indexes_to_create = [
                    ("chat_log", "site_id, created_at DESC", "idx_chatlog_site_time"),
                    ("chat_log", "site_id, confidence", "idx_chatlog_conf"),
                    ("intent", "site_id", "idx_intent_site"),
                    ("lead_capture", "site_id, captured_at DESC", "idx_leads_time"),
                    ("contact_request", "site_id, status", "idx_contact_status"),
                ]
            
            print("[*] Adding database indexes for dashboard optimization...\n")
            
            created_count = 0
            skipped_count = 0
            
            for table, cols, idx_name in indexes_to_create:
                try:
                    sql = f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})'
                    
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        print(f"[+] Created index: {idx_name} on {table}({cols})")
                        created_count += 1
                    except Exception as e:
                        err_str = str(e)
                        if 'already exists' in err_str or 'Duplicate' in err_str or 'UNIQUE constraint' in err_str:
                            print(f"[-] Skipped (already exists): {idx_name}")
                            skipped_count += 1
                        elif 'no such table' in err_str:
                            print(f"[-] Skipped (table not yet created): {table}")
                            skipped_count += 1
                        else:
                            print(f"[!] Failed: {idx_name} - {err_str[:80]}")
                except Exception as e:
                    print(f"[W] Error processing {idx_name}: {str(e)[:80]}")
            
            print(f"\n[Summary] {created_count} indexes created, {skipped_count} skipped")
            print("\n[OK] Dashboard optimization complete! Queries should now be faster.")

if __name__ == "__main__":
    try:
        add_dashboard_indexes()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
