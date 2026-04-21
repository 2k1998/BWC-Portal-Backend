"""
Fix admin user by assigning to a company.
Run this after create_admin.py if you're getting 403 errors.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.user import User
from app.models.company import Company


def fix_admin_company():
    """Assign admin user to a company."""
    db: Session = SessionLocal()
    
    try:
        # Get admin user
        admin = db.query(User).filter(User.email == "admin@bwc.com").first()
        
        if not admin:
            print("❌ Admin user not found. Run create_admin.py first.")
            return
        
        # Get or create a company
        company = db.query(Company).first()
        
        if not company:
            print("📝 No companies found. Creating default company...")
            company = Company(
                name="BWC Default Company"
            )
            db.add(company)
            db.commit()
            db.refresh(company)
            print(f"✅ Created company: {company.name}")
        
        # Assign admin to company
        if admin.company_id:
            print(f"ℹ️  Admin already assigned to company ID: {admin.company_id}")
        else:
            admin.company_id = company.id
            db.commit()
            print(f"✅ Assigned admin to company: {company.name} (ID: {company.id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Fixing admin user company assignment...")
    fix_admin_company()
    print("✨ Done!")
