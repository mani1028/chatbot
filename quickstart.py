#!/usr/bin/env python3
"""
Quick Start Script - Get the upgraded chatbot running in 3 steps
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a shell command and print status"""
    print(f"\n📝 {description}...")
    print(f"   Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ {description} completed")
        return True
    else:
        print(f"✗ {description} failed")
        if result.stderr:
            print(f"   Error: {result.stderr}")
        return False

def main():
    print("=" * 60)
    print("Enterprise Intent-Based Chatbot - Quick Start")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    # Step 1: Remove old database
    print("\n🗑️  Step 1: Removing old database...")
    if os.path.exists('chatbot.db'):
        try:
            os.remove('chatbot.db')
            print("   ✓ Old database removed")
        except Exception as e:
            print(f"   ⚠️  Could not remove database: {e}")
    else:
        print("   ℹ️  No existing database found")
    
    # Step 2: Initialize new database
    print("\n⚙️  Step 2: Creating new database schema...")
    if run_command(
        f"{sys.executable} -c \"from app import app; print('Database initialized')\"",
        "Database initialization"
    ):
        pass
    else:
        print("   Continuing anyway...")
    
    # Step 3: Seed intents
    print("\n🌱 Step 3: Seeding intents from JSON files...")
    if run_command(
        f"{sys.executable} seed_intents.py",
        "Intent seeding"
    ):
        pass
    else:
        print("   ⚠️  Intent seeding may have failed, but continuing...")
    
    # Done!
    print("\n" + "=" * 60)
    print("✓ Setup Complete!")
    print("=" * 60)
    
    print("\n📋 Next Steps:")
    print("   1. Start the server:")
    print(f"      python app.py")
    print("\n   2. Open in browser:")
    print(f"      http://localhost:5000")
    print("\n   3. Admin dashboard:")
    print(f"      http://localhost:5000/admin/login")
    print(f"      Default: admin / admin123")
    print("\n   4. Read documentation:")
    print(f"      - UPGRADE_GUIDE.md     (Complete upgrade guide)")
    print(f"      - MIGRATION_SUMMARY.md (Technical summary)")
    print("\n   5. (Optional) Clean up legacy files:")
    print(f"      python cleanup.py")
    
    print("\n" + "=" * 60)
    print("Happy chatting! 🚀")
    print("=" * 60)

if __name__ == '__main__':
    main()
