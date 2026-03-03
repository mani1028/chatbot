#!/usr/bin/env python3
import sqlite3
conn = sqlite3.connect('instance/chatbot.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print('Tables in database:')
for t in tables:
    print(f'  - {t}')
    if t == 'unanswered_questions':
        cursor.execute(f"PRAGMA table_info({t})")
        cols = cursor.fetchall()
        print(f"    Columns: {[c[1] for c in cols]}")
conn.close()
