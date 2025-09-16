#!/usr/bin/env python3
"""
Migration script to add head_id column to groups table
Run this script to add the team head functionality to existing groups
"""

import sqlite3
import os
from pathlib import Path

def run_migration():
    """Add head_id column to groups table"""
    db_path = "test.db"
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Please make sure you're in the Backend directory.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if head_id column already exists
        cursor.execute("PRAGMA table_info(groups)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'head_id' in columns:
            print("head_id column already exists in groups table.")
            return True
        
        # Add head_id column
        cursor.execute("ALTER TABLE groups ADD COLUMN head_id INTEGER REFERENCES users(id)")
        
        conn.commit()
        print("Successfully added head_id column to groups table.")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Running migration to add head_id to groups table...")
    success = run_migration()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
