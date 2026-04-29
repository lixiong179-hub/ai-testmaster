import requests

API = "http://localhost:8000/api/v1"
FRONTEND = "http://localhost:3000"

print("=" * 60)
print("  Login Debug - Full Simulation")
print("=" * 60)

# Step 1: Backend health
print("\n[1] Backend Health Check")
try:
    r = requests.get(f"{API.replace('/api/v1', '')}/health", timeout=5)
    print(f"    Status: {r.status_code} -> {r.text[:100]}")
except Exception as e:
    print(f"    ERROR: {e}")

# Step 2: Direct API login (what our Python tests do)
print("\n[2] Direct API Login (Python requests)")
r = requests.post(
    f"{API}/auth/login",
    data={"username": "admin", "password": "admin"},
    timeout=10,
)
print(f"    Status: {r.status_code}")
print(f"    Body:   {r.text[:300]}")

# Step 3: Simulate EXACTLY what the frontend does (URLSearchParams + form-urlencoded)
print("\n[3] Simulate Frontend Behavior (URLSearchParams style)")
from urllib.parse import urlencode
params = urlencode({"username": "admin", "password": "admin"})
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
}
r2 = requests.post(
    f"{API}/auth/login",
    data=params,
    headers=headers,
    timeout=10,
)
print(f"    Status: {r2.status_code}")
print(f"    Body:   {r2.text[:300]}")

# Step 4: Try through Vite proxy (like browser does)
print("\n[4] Through Frontend Proxy (port 3000)")
try:
    r3 = requests.post(
        f"{FRONTEND}/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    print(f"    Status: {r3.status_code}")
    print(f"    Body:   {r3.text[:300]}")
except Exception as e:
    print(f"    ERROR: {e}")

# Step 5: Try JSON format (which backend REJECTS)
print("\n[5] JSON Format (should be rejected by backend)")
r4 = requests.post(
    f"{API}/auth/login",
    json={"username": "admin", "password": "admin"},
    headers={"Content-Type": "application/json"},
    timeout=10,
)
print(f"    Status: {r4.status_code}")
print(f"    Body:   {r4.text[:200]}")

# Step 6: Check if token works for protected endpoint
print("\n[6] Token Validation Test")
if r.status_code == 200:
    token = r.json().get("data", {}).get("access_token", "")
    if token:
        r5 = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        print(f"    /auth/me with token: {r5.status_code}")
        print(f"    User info: {r5.text[:200]}")

        r6 = requests.get(
            f"{API}/project/list",
            params={"page": 1, "page_size": 5},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        print(f"    /project/list: {r6.status_code}")
        print(f"    Projects count in response: ...")

# Step 7: Check frontend accessibility
print("\n[7] Frontend Page Check")
try:
    rf = requests.get(f"{FRONTEND}/login", timeout=5)
    print(f"    /login page: {rf.status_code}, size={len(rf.content)} bytes")
    has_vue = 'id="app"' in rf.text or 'vue' in rf.text.lower()
    print(f"    Has Vue app mount point: {has_vue}")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "=" * 60)
print("  Debug Complete")
print("=" * 60)
