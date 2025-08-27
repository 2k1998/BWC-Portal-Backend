# reset_database.py - Complete with all models
import sys
import os

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from database import Base, engine
from sqlalchemy import text
# Import ALL your models here so SQLAlchemy knows about them
from models import (
    User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
    Notification, Contact, DailyCall, TaskHistory, Project,
    Sale, EmployeeCommissionRule, MonthlyCommissionSummary, Payment
)

def reset_database():
    """
    Drops all tables from the database and recreates them.
    WARNING: This will delete all existing data.
    """
    print("--- WARNING: This script will delete ALL data in your database. ---")
    user_confirmation = input("Are you sure you want to proceed? (yes/no): ")
    
    if user_confirmation.lower() != 'yes':
        print("Database reset cancelled.")
        return

    try:
        print("Dropping all tables with CASCADE...")
        
        # Use CASCADE to drop all dependent objects
        with engine.connect() as connection:
            # Disable foreign key checks temporarily (PostgreSQL specific)
            connection.execute(text("SET session_replication_role = replica;"))
            
            # Drop all tables with CASCADE
            Base.metadata.drop_all(bind=engine)
            
            # Re-enable foreign key checks
            connection.execute(text("SET session_replication_role = DEFAULT;"))
            connection.commit()
            
        print("All tables dropped successfully.")

        print("Creating all tables from scratch...")
        # create_all will create new tables based on your current models
        Base.metadata.create_all(bind=engine)
        print("Database has been reset successfully.")
        print("\nNew tables created:")
        print("- Users, Tasks, Groups, Companies, etc. (existing)")
        print("- Projects (project management)")
        print("- Sales (sales tracking)")
        print("- Employee Commission Rules (commission setup)")
        print("- Monthly Commission Summaries (commission calculations)")
        print("- Payments (payment management)")
        print("- Financial Summaries (financial overview)")
        print("\nRun 'python seed.py' to create initial data.")

    except Exception as e:
        print(f"An error occurred during the database reset: {e}")
        
        # If the above method fails, try the nuclear option
        print("Trying alternative method...")
        try:
            with engine.connect() as connection:
                # Get all table names
                result = connection.execute(text("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public';
                """))
                tables = [row[0] for row in result]
                
                # Drop each table with CASCADE
                for table in tables:
                    print(f"Dropping table: {table}")
                    connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                
                connection.commit()
                
            print("All tables dropped with CASCADE.")
            print("Creating all tables from scratch...")
            Base.metadata.create_all(bind=engine)
            print("Database has been reset successfully.")
            
        except Exception as e2:
            print(f"Alternative method also failed: {e2}")
            print("\nManual solution:")
            print("1. Connect to your PostgreSQL database")
            print("2. Run: DROP SCHEMA public CASCADE;")
            print("3. Run: CREATE SCHEMA public;")
            print("4. Run: python create_db.py")

if __name__ == "__main__":
    reset_database()