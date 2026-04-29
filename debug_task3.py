"""
Debug Routes - Test task creation with various formats
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Login first
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]

print("Testing Task Creation Formats")

# Test 1: JSON with all fields
print("\n[Test 1] JSON with all fields")
task_data = {
    "project_id": 1,
    "task_name": "TestTask_123",
    "description": "Auto test",
    "case_ids": []
}
resp = requests.post(
    f"{BASE_URL}/api/v1/test-task",
    json=task_data,
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 2: JSON without case_ids
print("\n[Test 2] JSON without case_ids")
task_data = {
    "project_id": 1,
    "task_name": "TestTask_456"
}
resp = requests.post(
    f"{BASE_URL}/api/v1/test-task",
    json=task_data,
    headers={"Authorization": f"Bearer {token}"}
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 3: Check OpenAPI schema for this endpoint
print("\n[Test 3] Check OpenAPI for test-task POST")
resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    endpoint = data.get("paths", {}).get("/api/v1/test-task", {}).get("post", {})
    print(f"Request body schema: {endpoint.get('requestBody', {})}")
