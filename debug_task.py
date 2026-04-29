"""
Debug Task Creation
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Login first
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("Testing Task Creation")

# Create task
task_data = {
    "project_id": 1,
    "task_name": "TestTask_123",
    "description": "Auto test created task",
    "case_ids": []
}

# Try with different paths
print("\n[Test] POST /api/v1/test-task")
resp = requests.post(f"{BASE_URL}/api/v1/test-task", json=task_data, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

print("\n[Test] POST /api/v1/test_task")
resp = requests.post(f"{BASE_URL}/api/v1/test_task", json=task_data, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
