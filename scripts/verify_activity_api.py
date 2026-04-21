import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000"

def login(email, password):
    url = f"{BASE_URL}/auth/login"
    data = json.dumps({"username_or_email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print(f"Login failed for {email}: {response.read().decode()}")
                return None
            return json.loads(response.read().decode())["access_token"]
    except urllib.error.HTTPError as e:
        print(f"Login failed for {email}: {e.code} {e.read().decode()}")
        return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_admin_access():
    print("\n--- Testing Admin Access ---")
    token = login("admin@example.com", "admin123") 
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Test Global Activity Log
    url = f"{BASE_URL}/activity-logs/admin"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
             if response.status == 200:
                print("[PASS] Admin can access global logs")
                data = json.loads(response.read().decode())
                print(f"       Total logs: {data.get('total', 0)}")
                if data.get('logs'):
                     print(f"       Sample: {data['logs'][0].get('action_type')} on {data['logs'][0].get('entity_type')}")
             else:
                print(f"[FAIL] Admin access denied: {response.status} {response.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"[FAIL] Admin access denied: {e.code} {e.read().decode()}")
    except Exception as e:
        print(f"[ERROR] {e}")

def test_user_access():
    print("\n--- Testing User Access ---")
    token = login("admin@example.com", "admin123") 
    if not token:
        return
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch a task first to get a valid ID
    url_tasks = f"{BASE_URL}/tasks"
    req_tasks = urllib.request.Request(url_tasks, headers=headers)
    
    task_id = None
    try:
        with urllib.request.urlopen(req_tasks) as response:
            data = json.loads(response.read().decode())
            if data.get('tasks'):
                task_id = data['tasks'][0]['id']
                print(f"       Testing with Task ID: {task_id}")
    except Exception as e:
        print(f"Could not fetch tasks: {e}")
        return

    if task_id:
        # Test Entity Log (Task)
        params = urllib.parse.urlencode({"entity_type": "Task", "entity_id": task_id})
        url = f"{BASE_URL}/activity-logs?{params}"
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print("[PASS] User can access entity logs for accessible task")
                else:
                    print(f"[FAIL] User denied access: {response.status}")
        except urllib.error.HTTPError as e:
            print(f"[FAIL] User denied access: {e.code} {e.read().decode()}")

if __name__ == "__main__":
    try:
        test_admin_access()
        test_user_access()
    except Exception as e:
        print(f"Test failed with exception: {e}")
