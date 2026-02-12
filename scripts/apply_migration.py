"""Apply SQL migration to the project's SQLite database.

Usage:
    python scripts/apply_migration.py scripts/migrations/001_add_workflow_clientconfig.sql

This reads the DB path from config.DATABASE_PATH and executes the SQL file.
"""
import sys
from pathlib import Path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python apply_migration.py <sql-file>')
        sys.exit(1)

    sql_file = Path(sys.argv[1])
    if not sql_file.exists():
        print('SQL file not found:', sql_file)
        sys.exit(1)

    # import config and sqlite3
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import DATABASE_PATH
    import sqlite3

    db_path = DATABASE_PATH
    print('Applying migration', sql_file, 'to', db_path)

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(sql)
        conn.commit()
        print('Migration applied successfully')
    except Exception as e:
        print('Migration failed:', e)
        conn.rollback()
    finally:
        conn.close()
