"""
Test login endpoint directly with requests library.
"""
import requests
import json

url = "http://127.0.0.1:8000/auth/login"

# Test with correct format
payload = {
    "username_or_email": "admin@bwc.com",
    "password": "admin123"
}

headers = {
    "Content-Type": "application/json"
}

print("🔐 Testing login endpoint...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("\n✅ Login successful!")
    else:
        print(f"\n❌ Login failed!")
        
except Exception as e:
    print(f"❌ Error: {e}")
