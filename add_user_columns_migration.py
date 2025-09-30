#!/usr/bin/env python3
"""
Database migration script to add missing columns to users table.
This script will:
1. Add the last_seen column to the users table
2. Add the is_online column to the users table
3. Add the permissions column to the users table (if missing)
4. Add Google Calendar columns (google_credentials, google_calendar_sync_enabled)
"""

from sqlalchemy import create_engine, text
from database import DB_URL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_users_add_columns():
    """Add missing columns to users table"""
    
    try:
        # Create engine
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # Check which columns are missing
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users'
            """))
            
            existing_columns = {row[0] for row in result.fetchall()}
            logger.info(f"Existing columns in users table: {existing_columns}")
            
            # Define columns that should exist
            required_columns = {
                'last_seen': 'TIMESTAMP WITH TIME ZONE',
                'is_online': 'BOOLEAN DEFAULT FALSE',
                'permissions': 'JSON DEFAULT \'[]\''
            }
            
            # Add missing columns
            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    logger.info(f"Adding {column_name} column to users table...")
                    conn.execute(text(f"""
                        ALTER TABLE users 
                        ADD COLUMN {column_name} {column_definition}
                    """))
                    logger.info(f"Added {column_name} column successfully")
                else:
                    logger.info(f"{column_name} column already exists")
            
            # Add Google Calendar columns (PostgreSQL syntax)
            if 'google_credentials' not in existing_columns:
                logger.info("Adding google_credentials column to users table...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN google_credentials JSON
                """))
                logger.info("Added google_credentials column successfully")
            else:
                logger.info("google_credentials column already exists")

            if 'google_calendar_sync_enabled' not in existing_columns:
                logger.info("Adding google_calendar_sync_enabled column to users table...")
                conn.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN google_calendar_sync_enabled BOOLEAN DEFAULT FALSE NOT NULL
                """))
                logger.info("Added google_calendar_sync_enabled column successfully")
            else:
                logger.info("google_calendar_sync_enabled column already exists")
            
            # Changes are auto-committed in this context
            
            logger.info("Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate_users_add_columns()
