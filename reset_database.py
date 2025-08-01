# reset_database.py - Fixed with all model imports
import sys
import os

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from database import Base, engine
# Import ALL your models here so SQLAlchemy knows about them
from models import (
    User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
    Notification, Contact, DailyCall, TaskHistory
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
        print("Dropping all tables...")
        # drop_all will delete all known tables from the database
        Base.metadata.drop_all(bind=engine)
        print("Tables dropped successfully.")

        print("Creating all tables from scratch...")
        # create_all will create new tables based on your current models
        Base.metadata.create_all(bind=engine)
        print("Database has been reset successfully.")
        print("You will need to register a new user account on the frontend.")

    except Exception as e:
        print(f"An error occurred during the database reset: {e}")

if __name__ == "__main__":
    reset_database()