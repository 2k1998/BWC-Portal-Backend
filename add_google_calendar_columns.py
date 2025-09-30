#!/usr/bin/env python3
"""
Database migration script to add Google Calendar integration columns to users table.
Run this manually: python add_google_calendar_columns.py
"""

from sqlalchemy import create_engine, text
from database import DB_URL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_google_calendar_columns():
    """Add Google Calendar columns to users table"""
    
    try:
        # Create engine
        engine = create_engine(DB_URL)
        is_sqlite = DB_URL.startswith('sqlite')
        
        with engine.connect() as conn:
            # Check which columns exist
            if is_sqlite:
                result = conn.execute(text("PRAGMA table_info(users);"))
                existing_columns = {row[1] for row in result.fetchall()}
            else:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'users'
                """))
                existing_columns = {row[0] for row in result.fetchall()}
            
            logger.info(f"Existing columns in users table: {existing_columns}")
            
            # Add google_credentials column
            if 'google_credentials' not in existing_columns:
                logger.info("Adding google_credentials column to users table...")
                if is_sqlite:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_credentials TEXT"))
                else:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_credentials JSON"))
                conn.commit()
                logger.info("Added google_credentials column successfully")
            else:
                logger.info("google_credentials column already exists")

            # Add google_calendar_sync_enabled column
            if 'google_calendar_sync_enabled' not in existing_columns:
                logger.info("Adding google_calendar_sync_enabled column to users table...")
                if is_sqlite:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_calendar_sync_enabled BOOLEAN DEFAULT 0 NOT NULL"))
                else:
                    conn.execute(text("ALTER TABLE users ADD COLUMN google_calendar_sync_enabled BOOLEAN DEFAULT FALSE NOT NULL"))
                conn.commit()
                logger.info("Added google_calendar_sync_enabled column successfully")
            else:
                logger.info("google_calendar_sync_enabled column already exists")
            
            logger.info("Google Calendar migration completed successfully!")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    add_google_calendar_columns()
