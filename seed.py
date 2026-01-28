# seed.py - Updated with all models including sales/commission system
import sys
import os
from sqlalchemy.orm import Session
from database import SessionLocal
# Import ALL models including the new ones
from models import (
    User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
    Notification, Contact, DailyCall, TaskHistory, Project,
    Sale, EmployeeCommissionRule, MonthlyCommissionSummary, Payment
)
from routers.auth import get_password_hash

# This ensures the script can find your other project files
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# --- Configuration for your default data ---

# 1. Define the default administrator account
ADMIN_EMAIL = "kabaniskostas1998@gmail.com"
ADMIN_PASSWORD = "Administrator"

# 2. Define the initial list of companies
INITIAL_COMPANIES = [
    {"name": "Revma Plus IKE"},
    {"name": "Revma Plus Retail AE"},
    {"name": "Revma Plus CC IKE"},
    {"name": "BWC ΙΚΕ"},
    {"name": "Best Solution Cars"},
]

# 3. Sample commission rules for the admin user
SAMPLE_COMMISSION_RULES = [
    {
        "sale_type": None,  # Applies to all sale types
        "base_commission_rate": 10.0,  # 10% base commission
        "min_sale_amount": 500.0,
        "tier1_threshold": 10000.0,  # €10,000 monthly target
        "tier1_bonus_rate": 2.0,     # +2% bonus
        "tier2_threshold": 20000.0,  # €20,000 monthly target  
        "tier2_bonus_rate": 3.0,     # +3% bonus
        "tier3_threshold": 30000.0,  # €30,000 monthly target
        "tier3_bonus_rate": 5.0,     # +5% bonus
    }
]

def seed_database():
    """
    Populates the database with initial data (admin user, companies, commission rules).
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
            db.refresh(new_admin)
            print(f"Admin user '{ADMIN_EMAIL}' created successfully.")
            admin_user = new_admin
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

        # --- Create Sample Commission Rules for Admin ---
        from datetime import date
        for rule_data in SAMPLE_COMMISSION_RULES:
            existing_rule = db.query(EmployeeCommissionRule).filter(
                EmployeeCommissionRule.employee_id == admin_user.id,
                EmployeeCommissionRule.sale_type == rule_data["sale_type"]
            ).first()
            
            if not existing_rule:
                new_rule = EmployeeCommissionRule(
                    employee_id=admin_user.id,
                    sale_type=rule_data["sale_type"],
                    base_commission_rate=rule_data["base_commission_rate"],
                    min_sale_amount=rule_data["min_sale_amount"],
                    tier1_threshold=rule_data["tier1_threshold"],
                    tier1_bonus_rate=rule_data["tier1_bonus_rate"],
                    tier2_threshold=rule_data["tier2_threshold"],
                    tier2_bonus_rate=rule_data["tier2_bonus_rate"],
                    tier3_threshold=rule_data["tier3_threshold"],
                    tier3_bonus_rate=rule_data["tier3_bonus_rate"],
                    effective_from=date.today(),
                    created_by_id=admin_user.id
                )
                db.add(new_rule)
                db.commit()
                print(f"Commission rule created for {admin_user.email}")
            else:
                print(f"Commission rule for {admin_user.email} already exists. Skipping.")

        print("\n" + "="*50)
        print("DATABASE SEEDING COMPLETE!")
        print("="*50)
        print(f"✅ Login credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("✅ Sample companies created")
        print("✅ Commission rules set up")
        print("\nYou can now:")
        print("1. Log in to the portal")
        print("2. Add sales and track commissions")
        print("3. Create projects and manage payments")
        print("="*50)

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()