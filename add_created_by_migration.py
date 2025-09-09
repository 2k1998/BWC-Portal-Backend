#!/usr/bin/env python3
"""
Database migration script to add created_by_id field to existing tasks.
This script will:
1. Add the created_by_id column to the tasks table
2. Set created_by_id to owner_id for existing tasks (assuming the owner was the creator)
"""

from sqlalchemy import create_engine, text
from database import DB_URL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_tasks_add_created_by():
    """Add created_by_id column to tasks table and populate it"""
    
    try:
        # Create engine
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # Check if column already exists (PostgreSQL syntax)
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.columns 
                WHERE table_name = 'tasks' AND column_name = 'created_by_id'
            """))
            
            column_exists = result.fetchone()[0] > 0
            
            if column_exists:
                logger.info("created_by_id column already exists in tasks table")
                return
            
            logger.info("Adding created_by_id column to tasks table...")
            
            # Add the column (SQLite doesn't support adding NOT NULL columns with foreign keys directly)
            conn.execute(text("""
                ALTER TABLE tasks 
                ADD COLUMN created_by_id INTEGER
            """))
            
            # Update existing tasks to set created_by_id = owner_id
            # (assuming the owner was originally the creator)
            logger.info("Setting created_by_id to owner_id for existing tasks...")
            result = conn.execute(text("""
                UPDATE tasks 
                SET created_by_id = owner_id 
                WHERE created_by_id IS NULL
            """))
            
            logger.info(f"Updated {result.rowcount} tasks with created_by_id")
            
            # Commit the changes
            conn.commit()
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate_tasks_add_created_by()
