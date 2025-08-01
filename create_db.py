# create_db.py - Fixed with all model imports
import sys
import os

# Add the project root to the sys.path to allow imports like 'database' and 'models'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from database import Base, engine
# Import ALL your models here so SQLAlchemy knows about them
from models import (
    User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
    Notification, Contact, DailyCall, TaskHistory
)

print("Attempting to create/update database tables...")
try:
    # This will create all tables based on your current models
    Base.metadata.create_all(bind=engine)
    print("Tables created/updated successfully.")
except Exception as e:
    print(f"An error occurred during table creation: {e}")
    print("Please ensure your PostgreSQL server is running and database credentials are correct.")