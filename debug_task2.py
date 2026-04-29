"""
Debug Routes - Check actual path
"""
import requests

BASE_URL = "http://localhost:8000"

# Login first
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

print("Testing Routes - POST with JSON")

# Test POST with JSON
import json
task_data = {
    "project_id": 1,
    "task_name": "TestTask_123",
    "description": "Auto test",
    "case_ids": []
}

print("\n[Test] POST /api/v1/test_task with JSON body")
resp = requests.post(
    f"{BASE_URL}/api/v1/test_task",
    data=json.dumps(task_data),
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

# Also test GET with path param
print("\n[Test] GET /api/v1/test-task/1")
resp = requests.get(f"{BASE_URL}/api/v1/test-task/1", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:200]}")
