#!/usr/bin/env python3
"""
Database migration script to add maintenance date columns to cars table.
This script adds:
- kteo_last_date
- kteo_next_date
- service_last_date
- service_next_date
- tire_change_date
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
            WHERE table_name = 'cars'
              AND table_schema = current_schema()
        """))
        return {row[0] for row in result.fetchall()}
    except Exception as exc:
        logger.info("PostgreSQL column lookup failed, trying SQLite: %s", exc)
        result = conn.execute(text("""
            SELECT name
            FROM pragma_table_info('cars')
        """))
        return {row[0] for row in result.fetchall()}


def migrate_cars_add_maintenance_dates():
    """Add missing maintenance date columns to cars table."""
    try:
        engine = create_engine(DB_URL)

        with engine.connect() as conn:
            existing_columns = _get_existing_columns(conn)
            logger.info("Existing columns in cars table: %s", existing_columns)

            required_columns = {
                "kteo_last_date": "DATE",
                "kteo_next_date": "DATE",
                "service_last_date": "DATE",
                "service_next_date": "DATE",
                "tire_change_date": "DATE",
            }

            for column_name, column_definition in required_columns.items():
                if column_name not in existing_columns:
                    logger.info("Adding %s column to cars table...", column_name)
                    conn.execute(text(f"""
                        ALTER TABLE cars
                        ADD COLUMN {column_name} {column_definition}
                    """))
                    logger.info("Added %s column successfully", column_name)
                else:
                    logger.info("%s column already exists", column_name)

            conn.commit()

            logger.info("Cars maintenance dates migration completed successfully!")

    except Exception as exc:
        logger.error("Cars maintenance dates migration failed: %s", exc)
        raise


if __name__ == "__main__":
    migrate_cars_add_maintenance_dates()
