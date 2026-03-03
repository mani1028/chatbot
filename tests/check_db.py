#!/usr/bin/env python3
import sqlite3
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print('Tables found:', len(tables))
for t in sorted(tables)[:15]:
    print(f'  - {t}')

# Check phase1_metrics
if 'phase1_metrics' in tables:
    print('\nphase1_metrics:')
    cursor.execute("SELECT COUNT(*) FROM phase1_metrics")
    print('  Records:', cursor.fetchone()[0])

# Check for site-like tables
print('\nLooking for site tables...')
for t in tables:
    if 'site' in t.lower():
        print(f'  Found: {t}')
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        print(f'    Count: {count}')

conn.close()
