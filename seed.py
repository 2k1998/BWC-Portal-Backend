# seed.py
import sys
import os
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, Notification  # <-- Add Notification
from routers.auth import get_password_hash # Import the hashing function

# This ensures the script can find your other project files
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# --- Configuration for your default data ---

# 1. Define the default administrator account
ADMIN_EMAIL = "kabaniskostas1998@gmail.com"
ADMIN_PASSWORD = "Administrator" # Use a simple password for local development

# 2. Define the initial list of companies
INITIAL_COMPANIES = [
    {"name": "Revma Plus IKE"},
    {"name": "Revma Plus Retail AE"},
    {"name": "Revma Plus CC IKE"},
    {"name": "BWC ΙΚΕ"},
    {"name": "Best Solution Cars"},
]

# ---------------------------------------------

def seed_database():
    """
    Populates the database with initial data (admin user and companies).
    This script is safe to run multiple times.
    """
    db = SessionLocal()
    print("Seeding database with initial data...")
    
    try:
        # --- Create Admin User ---
        admin_user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not admin_user:
            hashed_password = get_password_hash(ADMIN_PASSWORD)
            new_admin = User(
                email=ADMIN_EMAIL,
                hashed_password=hashed_password,
                role="admin",
                first_name="Default",
                surname="Admin"
            )
            db.add(new_admin)
            db.commit()
            print(f"Admin user '{ADMIN_EMAIL}' created successfully.")
        else:
            print(f"Admin user '{ADMIN_EMAIL}' already exists. Skipping.")

        # --- Create Initial Companies ---
        for company_data in INITIAL_COMPANIES:
            company = db.query(Company).filter(Company.name == company_data["name"]).first()
            if not company:
                new_company = Company(**company_data)
                db.add(new_company)
                db.commit()
                print(f"Company '{company_data['name']}' created successfully.")
            else:
                print(f"Company '{company_data['name']}' already exists. Skipping.")
        
        print("\nDatabase seeding complete!")
        print(f"You can log in with: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()

