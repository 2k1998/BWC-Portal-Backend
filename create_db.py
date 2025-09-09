# create_db.py - Updated with Sales and Payment models
import sys
import os

# Add the project root to the sys.path to allow imports like 'database' and 'models'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from database import Base, engine
# Import ALL your models here so SQLAlchemy knows about them
from models import (
    User, Task, Group, Company, PasswordResetToken, Event, Car, Rental, 
    Notification, Contact, DailyCall, TaskHistory, Project,
    Sale, EmployeeCommissionRule, MonthlyCommissionSummary, Payment,
    CarIncome, CarExpense, TaskAssignment, TaskConversation, TaskMessage, 
    TaskNotification, ChatConversation, ChatMessage, ApprovalRequest, 
    ApprovalNotification, Document  # <-- Added missing models
)

def main():
    print("Attempting to create/update database tables...")
    try:
        # This will create all tables based on your current models
        Base.metadata.create_all(bind=engine)
        print("Tables created/updated successfully.")
        print("New tables added:")
        print("- sales")
        print("- employee_commission_rules") 
        print("- monthly_commission_summaries")
        print("- payments")
    except Exception as e:
        print(f"An error occurred during table creation: {e}")
        print("Please ensure your PostgreSQL server is running and database credentials are correct.")

if __name__ == "__main__":
    main()