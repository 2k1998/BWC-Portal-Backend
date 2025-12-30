#!/usr/bin/env python3
"""
Database migration script to add missing columns to tasks table.
This script will:
1. Add columns needed for task metadata and deletion tracking if missing.
2. Normalize deadline_all_day to false when NULL.
"""

from sqlalchemy import create_engine, text
from database import DB_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_existing_columns(conn):
    try:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tasks'
        """))
        return {row[0] for row in result.fetchall()}
    except Exception as exc:
        logger.info("PostgreSQL column lookup failed, trying SQLite: %s", exc)
        result = conn.execute(text("""
            SELECT name
            FROM pragma_table_info('tasks')
        """))
        return {row[0] for row in result.fetchall()}


def migrate_tasks_add_columns():
    """Add missing columns to tasks table"""
    try:
        engine = create_engine(DB_URL)

        with engine.connect() as conn:
            existing_columns = _get_existing_columns(conn)
            logger.info("Existing columns in tasks table: %s", existing_columns)

            required_columns = {
                "deadline_all_day": "BOOLEAN DEFAULT FALSE",
                "completed_at": "TIMESTAMP",
                "deleted_at": "TIMESTAMP",
                "deleted_by_id": "INTEGER",
                "status_comments": "TEXT",
                "status_updated_at": "TIMESTAMP",
                "status_updated_by": "INTEGER",
            }

            added_columns = set()
            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    logger.info("Adding %s column to tasks table...", column_name)
                    conn.execute(text(f"""
                        ALTER TABLE tasks
                        ADD COLUMN {column_name} {column_definition}
                    """))
                    added_columns.add(column_name)
                    logger.info("Added %s column successfully", column_name)
                else:
                    logger.info("%s column already exists", column_name)

            available_columns = existing_columns | added_columns
            if "deadline_all_day" in available_columns:
                conn.execute(text("""
                    UPDATE tasks
                    SET deadline_all_day = FALSE
                    WHERE deadline_all_day IS NULL
                """))

            conn.commit()

            logger.info("Tasks migration completed successfully!")

    except Exception as exc:
        logger.error("Tasks migration failed: %s", exc)
        raise


if __name__ == "__main__":
    migrate_tasks_add_columns()
