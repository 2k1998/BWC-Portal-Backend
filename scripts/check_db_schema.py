import sys
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from app.core.config import settings

def check_schema():
    print(f"Connecting to: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else '...'}")
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version();")).scalar()
            print(f"DB Version: {ver}")
            
        insp = inspect(engine)
        if hasattr(insp, "get_table_names"):
             print(f"Tables: {insp.get_table_names()}")
             
        if "activity_logs" in insp.get_table_names():
            cols = insp.get_columns("activity_logs")
            print("Table 'activity_logs' columns:")
            for c in cols:
                print(f" - {c['name']}: {c['type']}")
        else:
            print("Table 'activity_logs' NOT FOUND!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
