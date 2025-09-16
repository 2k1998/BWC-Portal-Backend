#!/usr/bin/env python3
"""
Migration script to add head_id column to groups table
Run this script to add the team head functionality to existing groups
"""

import os
from pathlib import Path

# We support both SQLite (local dev) and PostgreSQL (Render)
from sqlalchemy import text
from database import engine

def run_migration():
    """Add head_id column to groups table for the active DB (PostgreSQL on Render)."""
    try:
        with engine.begin() as conn:
            # Detect database dialect
            dialect_name = conn.dialect.name
            if dialect_name == 'sqlite':
                # SQLite path (local dev)
                # Check columns via PRAGMA
                cols = conn.execute(text("PRAGMA table_info(groups)")).fetchall()
                existing = {c[1] for c in cols}
                if 'head_id' in existing:
                    print('head_id already exists (sqlite)')
                    return True
                conn.execute(text("ALTER TABLE groups ADD COLUMN head_id INTEGER REFERENCES users(id)"))
                print('Added head_id to groups (sqlite)')
                return True
            else:
                # PostgreSQL path (Render)
                result = conn.execute(text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'groups' AND column_name = 'head_id'
                    """
                )).fetchone()
                if result:
                    print('head_id already exists (postgres)')
                    return True
                # Add the column nullable to avoid failures, then add FK if desired
                conn.execute(text("ALTER TABLE groups ADD COLUMN head_id INTEGER"))
                # Add FK constraint if not present
                conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.table_constraints tc
                            WHERE tc.table_name = 'groups' AND tc.constraint_name = 'groups_head_id_fkey'
                        ) THEN
                            ALTER TABLE groups
                            ADD CONSTRAINT groups_head_id_fkey FOREIGN KEY (head_id) REFERENCES users(id);
                        END IF;
                    END$$;
                """))
                print('Added head_id to groups (postgres)')
                return True
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    print("Running migration to add head_id to groups table...")
    success = run_migration()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
