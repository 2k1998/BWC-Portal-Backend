import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import date, timedelta
import asyncio
from starlette.testclient import TestClient

# Setup Paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.department import Department
from app.models.notification import Notification
from app.main import app

# Database Setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

client = TestClient(app)

def setup_test_data():
    print("Setting up test data...")
    # 1. Create Company & Department
    company = db.query(Company).filter_by(name="Test Corp").first()
    if not company:
        company = Company(name="Test Corp")
        db.add(company)
        db.commit()
    
    dept = db.query(Department).filter_by(name="IT").first()
    if not dept:
        dept = Department(name="IT", company_id=company.id)
        db.add(dept)
        db.commit()

    # 2. Create Users
    # User A (Owner/Admin)
    user_a = db.query(User).filter_by(email="owner@test.com").first()
    if not user_a:
        user_a = User(
            email="owner@test.com", 
            username="owner_user",
            hashed_password="hashed_password", # We won't login via API auth for setup, just for id reference if needed, OR we allow raw login
            first_name="Owner", 
            last_name="User",
            user_type="Admin", # Admin to bypass some checks
        )
        # We need a real password for login
        from app.core.security import hash_password
        user_a.hashed_password = hash_password("password123")
        db.add(user_a)
        db.commit()
        
    # User B (Assignee)
    user_b = db.query(User).filter_by(email="assignee@test.com").first()
    if not user_b:
        user_b = User(
            email="assignee@test.com", 
            username="assignee_user",
            hashed_password="hashed_password",
            first_name="Assignee", 
            last_name="User",
            user_type="Employee",
        )
        from app.core.security import hash_password
        user_b.hashed_password = hash_password("password123")
        db.add(user_b)
        db.commit()

    # User C (Manager)
    user_c = db.query(User).filter_by(email="manager@test.com").first()
    if not user_c:
        user_c = User(
            email="manager@test.com", 
            username="manager_user",
            hashed_password="hashed_password",
            first_name="Manager", 
            last_name="User",
            user_type="Employee",
        )
        from app.core.security import hash_password
        user_c.hashed_password = hash_password("password123")
        db.add(user_c)
        db.commit()
        
    db.refresh(user_a)
    db.refresh(user_b)
    db.refresh(user_c)
    
    return user_a, user_b, user_c, company, dept

def get_token(email, password):
    resp = client.post("/auth/login", json={"username_or_email": email, "password": password})
    if resp.status_code != 200:
        print(f"Login failed for {email}: {resp.text}")
        return None
    return resp.json()["access_token"]

def verify_notifications():
    user_a, user_b, user_c, company, dept = setup_test_data()
    
    token_a = get_token("owner@test.com", "password123")
    token_b = get_token("assignee@test.com", "password123")
    token_c = get_token("manager@test.com", "password123")
    
    if not token_a or not token_b:
        print("Failed to get tokens. Exiting.")
        return

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_c = {"Authorization": f"Bearer {token_c}"}

    print("\n--- Diagnostic: Check DB Version and Schema ---")
    from sqlalchemy import text, inspect
    try:
        ver = db.execute(text("SELECT version();")).scalar()
        print(f"DB Version: {ver}")
        
        insp = inspect(engine)
        cols = insp.get_columns("activity_logs")
        print("Table 'activity_logs' columns:")
        for c in cols:
            print(f" - {c['name']}: {c['type']}")
    except Exception as e:
        print(f"Diagnostic failed: {e}")

    print("\n--- Test 0: Verify ActivityLog Insertion (Isolation Test) ---")
    try:
        from app.models.activity_log import ActivityLog
        from app.models.task import Task
        
        # 0a. Try with NULL JSON
        print("Test 0a: Insert with NULL JSON values...")
        dummy_log_null = ActivityLog(
            entity_type="Test",
            entity_id=uuid4(),
            action_type="TEST_NULL",
            performed_by_user_id=user_a.id,
            old_value=None,
            new_value=None
        )
        db.add(dummy_log_null)
        db.commit()
        print("SUCCESS: Manual ActivityLog insertion (NULL JSON) worked.")
        
        # 0b. Try with Dict JSON
        print("Test 0b: Insert with Dict JSON values...")
        dummy_log_json = ActivityLog(
            entity_type="Test",
            entity_id=uuid4(),
            action_type="TEST_JSON",
            performed_by_user_id=user_a.id,
            old_value={"test": "old"},
            new_value={"test": "new"}
        )
        db.add(dummy_log_json)
        db.commit()
        print("SUCCESS: Manual ActivityLog insertion (Dict JSON) worked.")
        
        # Cleanup
        db.delete(dummy_log_null)
        db.delete(dummy_log_json)
        db.commit()
    except Exception as e:
        print(f"FAILURE: Manual ActivityLog insertion failed: {e}")
        db.rollback()

    print("\n--- Test 1: Create Task (Expect ASSIGNMENT notification for B) ---")
    task_payload = {
        "title": f"Test Task {uuid4().hex[:6]}",
        "description": "Validation Task",
        "company_id": str(company.id),
        "department": dept.name,
        "priority": "Medium",
        "start_date": str(date.today()),
        "deadline": str(date.today() + timedelta(days=1)),
        "assigned_user_id": str(user_b.id),
        "urgency_label": "Urgent"
    }
    
    resp = client.post("/tasks", json=task_payload, headers=headers_a)
    if resp.status_code != 201:
        print(f"Create Task Failed: {resp.status_code} - {resp.text}")
    else:
        task_id = resp.json()["id"]
        print(f"Task Created: {task_id}")
        
        # Verify Notification
        notifs = db.query(Notification).filter(
            Notification.recipient_user_id == user_b.id, # B should get it
            Notification.read_status == "Unread",
            Notification.notification_type == "ASSIGNMENT"
        ).all()
        # Filter by recent
        notif = next((n for n in notifs if str(n.entity_id) == task_id), None)
        
        if notif:
            print("SUCCESS: Notification found for User B (Assignment)")
        else:
            print("FAILURE: No Assignment notification found for User B")

    print("\n--- Test 2: View Task / Status Change (Expect STATUS_CHANGE notification for A) ---")
    # User B views/statuses the task
    resp = client.post(f"/tasks/{task_id}/view", headers=headers_b)
    # Note: View action auto-updates "New" -> "Received"
    if resp.status_code != 200:
        print(f"View Task Failed: {resp.text}")
    else:
        print("Task Viewed (Status -> Received)")
        
        # Verify Notification for Owner (A)
        notifs = db.query(Notification).filter(
            Notification.recipient_user_id == user_a.id, 
            Notification.read_status == "Unread",
            Notification.notification_type == "STATUS_CHANGE"
        ).all()
        notif = next((n for n in notifs if str(n.entity_id) == task_id), None)
        
        if notif:
            print("SUCCESS: Notification found for User A (Status Change: Received)")
        else:
            print("FAILURE: No Status Change notification found for User A")

    print("\n--- Test 3: Transfer Task (Expect ASSIGNMENT for C) ---")
    # First, make task transferrable (Yellow/Not Urgent Not Important)
    # Only Owner can update metadata.
    update_payload = {"urgency_label": "Not Urgent & Not Important"}
    client.put(f"/tasks/{task_id}", json=update_payload, headers=headers_a)
    
    transfer_payload = {
        "new_assigned_user_id": str(user_c.id), # Transfer to C (Manager) - Assuming sub relationships allowed or Admin override
        "transfer_ownership": False
    }
    
    # We used User A (Admin) so they can transfer.
    resp = client.post(f"/tasks/{task_id}/transfer", json=transfer_payload, headers=headers_a)
    
    if resp.status_code != 200:
        print(f"Transfer Failed: {resp.text}")
        # Could be "Not subordinate" rule. Admin ignores it? 
        # API code: if current_user.user_type == "Admin": ... check `get_subordinate_ids`.
        # Wait, Admin doesn't automatically mean everyone is subordinate in `get_subordinate_ids`.
        # For validation, let's just create a new task assigned to A, then transfer to himself? No, can't transfer to self.
        # Let's Skip if rules are too tight for simple script, or assume Admin can do it.
    else:
        print("Task Transferred to C")
        
        # Verify Notification for C
        notifs = db.query(Notification).filter(
            Notification.recipient_user_id == user_c.id, 
            Notification.read_status == "Unread",
            Notification.notification_type == "ASSIGNMENT"
        ).all()
        notif = next((n for n in notifs if str(n.entity_id) == task_id), None)
        
        if notif:
            print("SUCCESS: Notification found for User C (Transfer/Assignment)")
        else:
            print("FAILURE: No Assignment notification found for User C")

    print("\n--- Test 4: Create Project (Expect ASSIGNMENT for Manager) ---")
    project_payload = {
        "name": f"Test Project {uuid4().hex[:6]}",
        "project_type": "Internal",
        "company_id": str(company.id),
        "priority": "High",
        "description": "Test Desc",
        "start_date": str(date.today()),
        "expected_completion_date": str(date.today() + timedelta(days=30)),
        "project_manager_user_id": str(user_c.id)
    }
    
    resp = client.post("/projects", json=project_payload, headers=headers_a)
    if resp.status_code != 201:
        print(f"Create Project Failed: {resp.text}")
    else:
        proj_id = resp.json()["id"]
        print(f"Project Created: {proj_id}")
        
        # Verify Notification for C
        notifs = db.query(Notification).filter(
            Notification.recipient_user_id == user_c.id, 
            Notification.notification_type == "ASSIGNMENT"
        ).all()
        notif = next((n for n in notifs if str(n.entity_id) == proj_id), None)
        
        if notif:
            print("SUCCESS: Notification found for User C (Project Manager)")
        else:
            print("FAILURE: No Project notification found for User C")

    print("\n--- Test 5: Verify Persistence (DB Check) ---")
    count = db.query(Notification).count()
    print(f"Total Notifications in DB: {count}")
    if count >= 3:
        print("SUCCESS: Notifications persisted.")
    else:
         print("WARNING: Count seems low.")

    print("\n--- Test 6: Mark All Read (Expect 0 Unread) ---")
    # Mark all read for User C
    resp = client.patch("/notifications/read-all", headers=headers_c)
    if resp.status_code != 200:
        print(f"Read All Failed: {resp.text}")
    else:
        # Verify count
        unread_c = db.query(Notification).filter(
            Notification.recipient_user_id == user_c.id,
            Notification.read_status == "Unread"
        ).count()
        
        if unread_c == 0:
            print("SUCCESS: All notifications marked as read for User C")
        else:
            print(f"FAILURE: User C still has {unread_c} unread notifications")

    print("\n--- Test 7: Edge Case - Orphaned Notification (Loose Coupling) ---")
    # 1. Create a throwaway task
    orphan_task_payload = {
        "title": f"Orphan Task {uuid4().hex[:6]}",
        "description": "This will be deleted",
        "company_id": str(company.id),
        "department": dept.name,
        "priority": "Low",
        "start_date": str(date.today()),
        "deadline": str(date.today() + timedelta(days=1)),
        "assigned_user_id": str(user_b.id),
        "urgency_label": "Not Urgent & Not Important"
    }
    resp = client.post("/tasks", json=orphan_task_payload, headers=headers_a)
    if resp.status_code != 201:
        print(f"Orphan Task Setup Failed: {resp.text}")
    else:
        o_task_id = resp.json()["id"]
        print(f"Task Created (to be deleted): {o_task_id}")
        
        # 2. Verify Notification exists
        notif = db.query(Notification).filter(
            Notification.recipient_user_id == user_b.id,
            Notification.entity_id == o_task_id
        ).first()
        
        if not notif:
            print("FAILURE: Setup failed - Notification not created initially.")
        else:
            print("Notification verified. Deleting Task from DB...")
            
            # 3. Delete Task manually (simulate DB deletion)
            # We need to delete via DB session to bypass API checks if we want raw deletion, 
            # or just use API if DELETE endpoint exists.
            # Using DB for "manually in DB" simulation.
            task_to_del = db.query(Task).filter(Task.id == o_task_id).first()
            if task_to_del:
                db.delete(task_to_del)
                db.commit()
                print("Task Deleted.")
            else:
                print("Task reference lost?")

            # 4. Verify Notification STILL exists
            # We need a new session or refresh to be sure? 
            # (In script, 'db' is same session, but commit refresh it)
            orphan_notif = db.query(Notification).filter(
                Notification.id == notif.id
            ).first()
            
            if orphan_notif:
                print("SUCCESS: Notification still exists (Loose Coupling Confirmed).")
                print(f" - Orphaned Entity ID: {orphan_notif.entity_id}")
                print(f" - Link (would 404): {orphan_notif.link}")
            else:
                print("FAILURE: Notification was deleted (CASCADE issue?)")

if __name__ == "__main__":
    verify_notifications()
