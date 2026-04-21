"""
Seed departments data into the database.
This script is idempotent - it will not create duplicate departments.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.department import Department


def seed_departments():
    """Seed default departments into the database."""
    db: Session = SessionLocal()
    
    try:
        # Define departments to seed
        departments_data = [
            "Ενέργεια",
            "Ασφάλειες",
            "Ακαδημία Αυτοβελτίωσης",
            "Ακίνητα",
            "Επενδύσεις",
            "Marketing/Κοινωνικά Δίκτυα",
            "Τηλεπικοινωνίες",
            "Cars",
        ]
        
        created_count = 0
        skipped_count = 0
        
        for dept_name in departments_data:
            # Check if department already exists
            existing_dept = db.query(Department).filter(Department.name == dept_name).first()
            
            if existing_dept:
                print(f"⏭️  Department '{dept_name}' already exists, skipping...")
                skipped_count += 1
                continue
            
            # Create new department
            department = Department(name=dept_name)
            db.add(department)
            created_count += 1
            print(f"✅ Created department: {dept_name}")
        
        db.commit()
        
        print(f"\n📊 Summary:")
        print(f"   Created: {created_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Total: {len(departments_data)}")
        
    except Exception as e:
        print(f"❌ Error seeding departments: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding departments...")
    seed_departments()
    print("✨ Done!")
