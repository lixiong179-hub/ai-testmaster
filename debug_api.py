"""
Debug API Endpoints
"""
import requests

BASE_URL = "http://localhost:8000"

# Login first
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("=" * 50)
print("Testing API Endpoints")
print("=" * 50)

# Test 1: test-task endpoint
print("\n[Test] GET /api/v1/test-task")
resp = requests.get(f"{BASE_URL}/api/v1/test-task", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 2: test-task without hyphen
print("\n[Test] GET /api/v1/test_task")
resp = requests.get(f"{BASE_URL}/api/v1/test_task", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 3: test-case endpoint
print("\n[Test] GET /api/v1/test-case")
resp = requests.get(f"{BASE_URL}/api/v1/test-case", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 4: test_case without hyphen
print("\n[Test] GET /api/v1/test_case")
resp = requests.get(f"{BASE_URL}/api/v1/test_case", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 5: case endpoint
print("\n[Test] GET /api/v1/case")
resp = requests.get(f"{BASE_URL}/api/v1/case", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")

# Test 6: user endpoint
print("\n[Test] GET /api/v1/user")
resp = requests.get(f"{BASE_URL}/api/v1/user", headers=headers)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:200]}")

print("\n" + "=" * 50)
