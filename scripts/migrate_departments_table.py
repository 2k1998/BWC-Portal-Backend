# scripts/migrate_departments_table.py
from sqlalchemy import MetaData, Table, Column, Integer, String, Boolean, DateTime, UniqueConstraint
from sqlalchemy.engine.reflection import Inspector
from datetime import datetime
from database import engine

def ensure_departments_table():
    meta = MetaData()
    meta.bind = engine
    insp = Inspector.from_engine(engine)

    if "departments" in insp.get_table_names():
        print("[OK] departments already exists")
        return

    Table(
        "departments",
        meta,
        Column("id", Integer, primary_key=True),
        Column("name", String(128), nullable=False, unique=True, index=True),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("created_by", Integer, nullable=True),
        UniqueConstraint("name", name="uq_department_name"),
    )
    meta.create_all(engine)
    print("[OK] created departments")

if __name__ == "__main__":
    ensure_departments_table()
