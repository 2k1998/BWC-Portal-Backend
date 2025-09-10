#!/usr/bin/env python3
"""
Migration to add created_by_id column to projects table
"""

from sqlalchemy import create_engine, text
from database import DB_URL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_projects_add_created_by():
    """Add created_by_id column to projects table and populate it"""
    
    try:
        logger.info(f"Starting projects migration with DB_URL: {DB_URL}")
        
        # Create engine
        engine = create_engine(DB_URL)
        
        with engine.connect() as conn:
            # Check if column already exists (PostgreSQL syntax)
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.columns 
                WHERE table_name = 'projects' AND column_name = 'created_by_id'
            """))
            
            column_exists = result.fetchone()[0] > 0
            logger.info(f"Column exists check result: {column_exists}")
            
            if column_exists:
                logger.info("created_by_id column already exists in projects table")
                return
            
            logger.info("Adding created_by_id column to projects table...")
            
            # Add the column (PostgreSQL syntax)
            conn.execute(text("""
                ALTER TABLE projects 
                ADD COLUMN created_by_id INTEGER REFERENCES users(id)
            """))
            
            logger.info("Column added successfully")
            
            # Commit the transaction
            conn.commit()
            
            # Now populate the column with a default user (first admin user)
            logger.info("Populating created_by_id column...")
            
            # Get the first admin user
            admin_result = conn.execute(text("""
                SELECT id FROM users WHERE role = 'admin' LIMIT 1
            """))
            
            admin_user = admin_result.fetchone()
            if admin_user:
                admin_id = admin_user[0]
                logger.info(f"Found admin user with ID: {admin_id}")
                
                # Update all projects to have this admin as creator
                conn.execute(text("""
                    UPDATE projects 
                    SET created_by_id = :admin_id 
                    WHERE created_by_id IS NULL
                """), {"admin_id": admin_id})
                
                logger.info("Projects updated with admin user as creator")
            else:
                # If no admin user, get the first user
                user_result = conn.execute(text("""
                    SELECT id FROM users ORDER BY id LIMIT 1
                """))
                
                first_user = user_result.fetchone()
                if first_user:
                    user_id = first_user[0]
                    logger.info(f"No admin found, using first user with ID: {user_id}")
                    
                    conn.execute(text("""
                        UPDATE projects 
                        SET created_by_id = :user_id 
                        WHERE created_by_id IS NULL
                    """), {"user_id": user_id})
                    
                    logger.info("Projects updated with first user as creator")
                else:
                    logger.warning("No users found in database, created_by_id will remain NULL")
            
            # Commit the updates
            conn.commit()
            logger.info("Projects migration completed successfully")
            
    except Exception as e:
        logger.error(f"Projects migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate_projects_add_created_by()
