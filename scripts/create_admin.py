"""
Create initial admin user.
This script is idempotent - it will not create duplicate admin users.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.page import Page
from app.models.permission import UserPagePermission


def create_admin_user(
    email: str = "admin@bwc.com",
    username: str = "admin",
    first_name: str = "System",
    last_name: str = "Administrator",
    password: str = "admin123"
):
    """Create initial admin user with full permissions on all pages."""
    db: Session = SessionLocal()
    
    try:
        # Check if admin user already exists
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        
        if existing_user:
            print(f"⏭️  Admin user already exists (email: {existing_user.email}, username: {existing_user.username})")
            print(f"   Skipping creation...")
            return
        
        # Create admin user
        admin_user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hash_password(password),
            user_type="Admin",
            is_active=True,
            force_password_change=False,  # No forced password change for initial admin
            manager_id=None
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"✅ Created admin user:")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"   ⚠️  CHANGE THIS PASSWORD IMMEDIATELY IN PRODUCTION!")
        
        # Get all pages
        pages = db.query(Page).all()
        
        if not pages:
            print(f"\n⚠️  No pages found in database. Run seed_pages.py first.")
            return
        
        # Grant full access to all pages
        permissions_created = 0
        for page in pages:
            permission = UserPagePermission(
                user_id=admin_user.id,
                page_id=page.id,
                access="full"
            )
            db.add(permission)
            permissions_created += 1
        
        db.commit()
        
        print(f"\n✅ Granted full access to {permissions_created} pages")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("👤 Creating admin user...")
    create_admin_user()
    print("✨ Done!")
