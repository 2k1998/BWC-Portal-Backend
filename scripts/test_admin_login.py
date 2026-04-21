"""
Test admin login credentials directly against the database.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import verify_password
from app.models.user import User


def test_admin_login():
    """Test if admin credentials work."""
    db: Session = SessionLocal()
    
    try:
        # Get admin user
        admin = db.query(User).filter(User.email == "admin@bwc.com").first()
        
        if not admin:
            print("❌ Admin user not found!")
            return
        
        print(f"✅ Found admin user:")
        print(f"   Email: {admin.email}")
        print(f"   Username: {admin.username}")
        print(f"   User Type: {admin.user_type}")
        print(f"   Is Active: {admin.is_active}")
        
        # Test password
        test_password = "admin123"
        if verify_password(test_password, admin.hashed_password):
            print(f"\n✅ Password '{test_password}' is CORRECT!")
        else:
            print(f"\n❌ Password '{test_password}' is INCORRECT!")
            print("   The admin password may have been changed.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🔐 Testing admin login credentials...\n")
    test_admin_login()
