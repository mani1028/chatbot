#!/usr/bin/env python3
"""
Migration script to add template_file column to intents table
Run this once to update the database schema
"""
import sqlite3

DB_PATH = 'instance/chatbot.db'

def migrate():
    """Add template_file column if it doesn't exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if column already exists
        c.execute("PRAGMA table_info(intents)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'template_file' in columns:
            print("[OK] template_file column already exists")
            conn.close()
            return True
        
        # Add the column
        print("[INFO] Adding template_file column to intents table...")
        c.execute('''
            ALTER TABLE intents 
            ADD COLUMN template_file VARCHAR(255) DEFAULT NULL
        ''')
        
        conn.commit()
        print("[OK] Migration complete - template_file column added")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == '__main__':
    success = migrate()
    exit(0 if success else 1)
