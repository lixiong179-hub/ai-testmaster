"""
Debug Routes
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

print("Testing Routes")

# Test with Form data instead of JSON
print("\n[Test] POST /api/v1/test-task with Form data")
form_data = {
    "project_id": "1",
    "task_name": "TestTask_123",
    "description": "Auto test",
    "case_ids": "[]"
}
resp = requests.post(f"{BASE_URL}/api/v1/test-task", data=form_data, headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

# Check OpenAPI docs
print("\n[Test] Check /docs endpoint")
resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = list(data.get("paths", {}).keys())
    print("Available paths containing 'task':")
    for p in sorted(paths):
        if "task" in p.lower():
            print(f"  {p}")
