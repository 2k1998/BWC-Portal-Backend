# Backend/scripts/migrate_completed_at.py
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from database import engine

SQL = """
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_completed_at ON tasks(completed_at);
"""

if __name__ == "__main__":
    with engine.begin() as conn:
        conn.execute(text(SQL))
    print("✅ Migration applied: completed_at + index")
