"""
Seed pages data into the database.
This script is idempotent - it will not create duplicate pages.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.page import Page


def seed_pages():
    """Seed default pages into the database."""
    db: Session = SessionLocal()
    
    try:
        # Define pages to seed
        pages_data = [
            {"label": "Dashboard", "key": "dashboard"},
            {"label": "Tasks", "key": "tasks"},
            {"label": "Teams", "key": "teams"},
            {"label": "Companies", "key": "companies"},
            {"label": "Contacts", "key": "contacts"},
            {"label": "Events", "key": "events"},
            {"label": "Documents", "key": "documents"},
            {"label": "Payments", "key": "payments"},
            {"label": "Cars", "key": "cars"},
            {"label": "Analytics", "key": "analytics"},
            {"label": "Admin Panel", "key": "admin"},
            {"label": "Chat", "key": "chat"},
        ]
        
        created_count = 0
        skipped_count = 0
        
        for page_data in pages_data:
            # Check if page already exists
            existing_page = db.query(Page).filter(Page.key == page_data["key"]).first()
            
            if existing_page:
                print(f"⏭️  Page '{page_data['label']}' already exists, skipping...")
                skipped_count += 1
                continue
            
            # Create new page
            page = Page(
                label=page_data["label"],
                key=page_data["key"]
            )
            db.add(page)
            created_count += 1
            print(f"✅ Created page: {page_data['label']}")
        
        db.commit()
        
        print(f"\n📊 Summary:")
        print(f"   Created: {created_count}")
        print(f"   Skipped: {skipped_count}")
        print(f"   Total: {len(pages_data)}")
        
    except Exception as e:
        print(f"❌ Error seeding pages: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding pages...")
    seed_pages()
    print("✨ Done!")
