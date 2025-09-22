#!/usr/bin/env python3
"""
Migration script to add permissions field to users table
This script ensures the permissions JSON field is properly configured
"""

import sqlite3
import json
from pathlib import Path

def migrate_database():
    """Add permissions field to users table if it doesn't exist"""
    
    # Database path
    db_path = Path(__file__).parent / "test.db"
    
    if not db_path.exists():
        print("Database not found. Please run the main application first to create the database.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if permissions column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'permissions' not in columns:
            print("Adding permissions column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '{}'")
            print("✓ Permissions column added successfully")
        else:
            print("✓ Permissions column already exists")
        
        # Update existing users to have empty permissions object
        cursor.execute("UPDATE users SET permissions = '{}' WHERE permissions IS NULL")
        updated_rows = cursor.rowcount
        print(f"✓ Updated {updated_rows} users with empty permissions")
        
        # Commit changes
        conn.commit()
        print("✓ Migration completed successfully")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
