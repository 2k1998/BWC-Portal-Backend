import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db

import random
import string

# ... existing imports ...

# Use TestClient
client = TestClient(app)

def login_as_admin():
    # Try default credentials from create_admin.py
    creds = [
        ("admin@bwc.com", "admin123"),
        ("admin@example.com", "admin")
    ]
    
    for email, password in creds:
        response = client.post("/auth/login", json={
            "username_or_email": email,
            "password": password
        })
        if response.status_code == 200:
            print(f"✅ Logged in as {email}")
            return response.json()["access_token"]
            
    print(f"FAILED to login as admin with any known credentials")
    return None

def verify_auth_hardening(admin_token):
    print("\n--- 1. Auth Hardening ---")
    
    # 1.1 Verify No Register
    resp = client.post("/auth/register", json={"email": "test@test.com", "password": "pass"})
    if resp.status_code == 404:
        print("✅ /auth/register is GONE (404)")
    else:
        print(f"❌ /auth/register exists! ({resp.status_code})")

    # 1.2 Verify No Change Password
    if not admin_token: return
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    resp = client.post("/auth/change-password", headers=headers, json={"old": "admin", "new": "new"})
    if resp.status_code == 404:
        print("✅ /auth/change-password is GONE (404)")
    else:
        print(f"❌ /auth/change-password exists! ({resp.status_code})")

def verify_admin_user_mgmt(admin_token):
    print("\n--- 2. Admin User Management ---")
    if not admin_token: return
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Randomize user to avoid collisions/stale state
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    email = f"phase8_{rand_suffix}@example.com"
    username = f"phase8_{rand_suffix}"
    
    # 2.1 Create User
    new_user_data = {
        "email": email,
        "username": username,
        "first_name": "Test",
        "last_name": "User",
        "user_type": "Agent", # Valid type
        "manager_id": None
    }
    
    resp = client.post("/admin/users", headers=headers, json=new_user_data)
    user_id = None
    if resp.status_code == 201:
        data = resp.json()
        if "generated_password" in data:
            print(f"✅ Create User returns 'generated_password' (ID: {data['user_id']})")
            user_id = data["user_id"]
        else:
            print(f"❌ Create User MISSING 'generated_password': {data}")
    elif resp.status_code == 400 and "already registered" in resp.text:
         print("⚠️ User already exists, skipping create verify")
         users = client.get("/admin/users", headers=headers).json().get("users", [])
         for u in users:
             if u["email"] == email:
                 user_id = u["id"]
                 break
    else:
        print(f"❌ Create User failed: {resp.text}")
        
    # 2.2 Reset Password
    if user_id:
        print(f"DEBUG: Verifying user existence via GET /admin/users/{user_id}")
        check_resp = client.get(f"/admin/users/{user_id}", headers=headers)
        print(f"DEBUG: User exists? {check_resp.status_code}")
        
        print(f"DEBUG: Attempting to reset password for user_id={user_id}")
        resp = client.post(f"/admin/users/{user_id}/reset-password", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if "generated_password" in data:
                print("✅ Reset Password returns 'generated_password'")
            else:
                print("❌ Reset Password MISSING 'generated_password'")
        else:
            print(f"❌ Reset Password failed: {resp.text}")
    else:
        print("⚠️ Skipping Reset Password test as no user_id available")

def verify_business_logic(admin_token):
    print("\n--- 3. Business Logic ---")
    if not admin_token: return
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get Admin ID for assignment
    me_resp = client.get("/admin/users/me", headers=headers)
    if me_resp.status_code == 200:
        admin_id = me_resp.json()["id"]
    else:
        print("❌ Failed to get admin info")
        return

    # 3.1 Create Task
    task_data = {
        "title": "Phase 8 Verif Task",
        "description": "Test",
        "urgency_label": "Urgent & Important", # valid value per error msg
        "priority": "High",
        "start_date": "2026-02-12",
        "deadline": "2026-02-13",
        "department": "IT", # Valid seeded department
        "company_id": "00000000-0000-0000-0000-000000000000", # Placeholder
        "assigned_user_id": admin_id # Assign to admin
    }
    
    # Need a valid company and department
    # Fetch companies
    resp = client.get("/companies", headers=headers)
    print(f"DEBUG: GET /companies status={resp.status_code}, response={resp.text[:100]}")
    companies = resp.json()
    
    if isinstance(companies, dict) and "detail" in companies:
        print(f"❌ Failed to list companies: {companies}")
        return

    if not companies.get("companies"):
        print("⚠️ No companies found. Creating default company.")
        # Admin can create company
        resp = client.post("/admin/companies", headers=headers, json={"name": "Test Company", "occupation": "IT"})
        if resp.status_code == 201:
            companies = {"companies": [resp.json()]}
            print("✅ Created Test Company")
        else:
             print(f"❌ Could not create company: {resp.status_code} {resp.text}")
             return

    task_data["company_id"] = companies["companies"][0]["id"]
    task_data["department"] = "IT" # Valid seeded department
    
    # Debug company ID
    print(f"DEBUG: Using company_id={task_data['company_id']}")
    
    resp = client.post("/tasks", headers=headers, json=task_data)
    if resp.status_code == 201:
        print("✅ Task Created")
        task_id = resp.json()["id"]
        
        # 3.2 Invalid Transition
        # New -> Completed (Invalid)
        resp = client.put(f"/tasks/{task_id}/status", headers=headers, json={"status": "Completed"})
        if resp.status_code == 400:
            print("✅ Invalid Transition (New -> Completed) blocked (400)")
        else:
            print(f"❌ Invalid Transition ALLOWED! ({resp.status_code})")
            
        # 3.3 Valid Transition
        # New -> Received (Implicit via view) or Explicit?
        # Explicit status update to Received is valid from New
        resp = client.put(f"/tasks/{task_id}/status", headers=headers, json={"status": "Received"})
        if resp.status_code == 200:
            print("✅ New -> Received transition allowed")
        else:
            print(f"❌ New -> Received transition failed: {resp.text}")

        # 3.4 Invalid Transfer (Red Urgency)
        # Should fail because urgency is Red
        # Need another user to transfer to
        users = client.get("/admin/users", headers=headers).json()["users"]
        if len(users) > 1:
            other_user = users[1]["id"]
            if other_user == users[0]["id"]: other_user = users[0]["id"] # fallback logic error
            
            resp = client.post(f"/tasks/{task_id}/transfer", headers=headers, json={
                "new_assigned_user_id": other_user
            })
            if resp.status_code == 400 and "Not Urgent & Not Important" in resp.text:
                print("✅ Transfer blocked due to Urgency (400)")
            else:
                print(f"❌ Transfer Check Failed: {resp.status_code} {resp.text}")
    else:
        print(f"❌ Create Task failed: {resp.text}")

if __name__ == "__main__":
    admin_token = login_as_admin()
    if admin_token:
        verify_auth_hardening(admin_token)
        verify_admin_user_mgmt(admin_token)
        verify_business_logic(admin_token)
    else:
        print("Cannot proceed without admin token")
