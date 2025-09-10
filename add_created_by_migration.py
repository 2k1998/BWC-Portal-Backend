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
        logger.info(f"Starting migration with DB_URL: {DB_URL}")
        
        # Create engine
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # Check if column already exists - try PostgreSQL first, then SQLite
            try:
                result = conn.execute(text("""
                    SELECT COUNT(*) as count 
                    FROM information_schema.columns 
                    WHERE table_name = 'tasks' AND column_name = 'created_by_id'
                """))
                column_exists = result.fetchone()[0] > 0
                logger.info(f"PostgreSQL column exists check result: {column_exists}")
            except Exception as e:
                logger.info(f"PostgreSQL check failed, trying SQLite: {e}")
                try:
                    result = conn.execute(text("""
                        SELECT COUNT(*) as count 
                        FROM pragma_table_info('tasks') 
                        WHERE name = 'created_by_id'
                    """))
                    column_exists = result.fetchone()[0] > 0
                    logger.info(f"SQLite column exists check result: {column_exists}")
                except Exception as e2:
                    logger.error(f"Both PostgreSQL and SQLite checks failed: {e2}")
                    raise
            
            if column_exists:
                logger.info("created_by_id column already exists in tasks table")
                return
            
            logger.info("Adding created_by_id column to tasks table...")
            
            # Add the column
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
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    migrate_tasks_add_created_by()
