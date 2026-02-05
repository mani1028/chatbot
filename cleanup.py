"""
Cleanup Script - Remove unwanted/legacy files
Run this to clean up old files no longer needed in the enterprise system
"""

import os
import shutil

# Files to delete (relative to chatbot root)
FILES_TO_DELETE = [
    'test_chatbot.py',
    'DEVELOPER_GUIDE.md',
    'DOCUMENTATION.md',
    'FILE_LISTING.md',
    'INDEX.md',
    'PROJECT_SUMMARY.md',
    'QUICK_START.md',
    'START_HERE.md',
    'WELCOME.txt'
]

# Directories to delete
DIRS_TO_DELETE = [
    '__pycache__',
    'instance'
]

def cleanup():
    """Remove legacy files and directories"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 50)
    print("Cleanup Script - Remove Legacy Files")
    print("=" * 50)
    
    # Delete individual files
    for filename in FILES_TO_DELETE:
        filepath = os.path.join(base_dir, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"✓ Deleted: {filename}")
            except Exception as e:
                print(f"✗ Error deleting {filename}: {str(e)}")
        else:
            print(f"⊘ Not found: {filename}")
    
    # Delete directories
    for dirname in DIRS_TO_DELETE:
        dirpath = os.path.join(base_dir, dirname)
        if os.path.exists(dirpath):
            try:
                shutil.rmtree(dirpath)
                print(f"✓ Deleted directory: {dirname}")
            except Exception as e:
                print(f"✗ Error deleting directory {dirname}: {str(e)}")
        else:
            print(f"⊘ Directory not found: {dirname}")
    
    print("=" * 50)
    print("Cleanup complete!")
    print("=" * 50)

if __name__ == '__main__':
    response = input("This will delete legacy files. Continue? (yes/no): ")
    if response.lower() == 'yes':
        cleanup()
    else:
        print("Cleanup cancelled")
