import sys
import os
from pathlib import Path
from sqlalchemy import text

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.core.database import SessionLocal

def verify_indexes():
    db = SessionLocal()
    try:
        tables = ["tasks", "projects", "events", "documents"]
        print("🔎 Verifying Indexes for tables: " + ", ".join(tables))
        
        for table in tables:
            print(f"\n📋 Indexes for table '{table}':")
            query = text(f"SELECT indexname, indexdef FROM pg_indexes WHERE tablename = '{table}';")
            result = db.execute(query)
            indexes = result.fetchall()
            
            if not indexes:
                print("   ❌ No indexes found!")
            else:
                for idx in indexes:
                    print(f"   ✅ {idx.indexname}")
                    # print(f"      Definition: {idx.indexdef}")

    except Exception as e:
        print(f"❌ Error verifying indexes: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_indexes()
