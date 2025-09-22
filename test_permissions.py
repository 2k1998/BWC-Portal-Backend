#!/usr/bin/env python3
"""
Test script for permission management endpoints
"""

import requests
import json

# Configuration
BASE_URL = "https://bwc-portal-backend-w1qr.onrender.com"  # Update with your backend URL
# For local testing, use: BASE_URL = "http://localhost:8000"

def test_permissions():
    """Test the permission management endpoints"""
    
    # Test data
    test_user_id = 1  # Update with a real user ID
    test_permissions = {
        "dashboard": True,
        "tasks": True,
        "projects": False,
        "companies": True,
        "users": False
    }
    
    print("Testing Permission Management Endpoints")
    print("=" * 50)
    
    # Note: You'll need to get a valid admin token first
    # This is just a template for testing
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer YOUR_ADMIN_TOKEN_HERE"  # Replace with actual token
    }
    
    # Test 1: Get user permissions
    print("\n1. Testing GET /users/{user_id}/permissions")
    try:
        response = requests.get(f"{BASE_URL}/users/{test_user_id}/permissions", headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Update user permissions
    print("\n2. Testing PUT /users/{user_id}/permissions")
    try:
        data = {"permissions": test_permissions}
        response = requests.put(f"{BASE_URL}/users/{test_user_id}/permissions", 
                              headers=headers, 
                              json=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Verify permissions were updated
    print("\n3. Verifying updated permissions")
    try:
        response = requests.get(f"{BASE_URL}/users/{test_user_id}/permissions", headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("To test the permission endpoints:")
    print("1. Get an admin token by logging in")
    print("2. Update the BASE_URL and test_user_id variables")
    print("3. Replace YOUR_ADMIN_TOKEN_HERE with the actual token")
    print("4. Run this script")
    test_permissions()
