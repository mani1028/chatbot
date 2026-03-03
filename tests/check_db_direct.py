"""
Check if phrase was actually added
"""
import sqlite3

conn = sqlite3.connect(r"C:\Users\HP\OneDrive\Desktop\chatbot\instance\chatbot.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("[CHECK 1] Does phrase exist in intent_phrases table?")
print("=" * 70)

cursor.execute("""
    SELECT id, intent_id, phrase
    FROM intent_phrases 
    WHERE phrase = 'pricing insurance'
""")

rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"[OK] Found phrase:")
        print(f"  - ID: {row['id']}")
        print(f"  - Intent ID: {row['intent_id']}")
        print(f"  - Phrase: {row['phrase']}")
else:
    print("[ERROR] Phrase NOT found in table!")

print("\n[CHECK 2] List all phrases for intent_id=9")
print("=" * 70)

cursor.execute("""
    SELECT id, phrase FROM intent_phrases 
    WHERE intent_id = 9
    ORDER BY id DESC
    LIMIT 10
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} phrases for intent_id=9:")
for row in rows:
    print(f"  - ID {row['id']}: '{row['phrase']}'")

print("\n[CHECK 3] Unknown intent logs for 'pricing insurance'")
print("=" * 70)

cursor.execute("""
    SELECT id, message, resolved, site_id FROM unknown_intent_logs 
    WHERE message = 'pricing insurance'
    ORDER BY id DESC
""")

rows = cursor.fetchall()
print(f"Found {len(rows)} unknown logs:")
for row in rows:
    print(f"  - ID: {row['id']}, Resolved: {row['resolved']}, Site ID: {row['site_id']}")

conn.close()
