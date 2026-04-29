import requests

print("=== 1. Check Backend Health ===")
try:
    r = requests.get("http://localhost:8000/health", timeout=5)
    print(f"Backend health: {r.status_code} -> {r.text[:200]}")
except Exception as e:
    print(f"Backend DOWN: {e}")

print()
print("=== 2. Test Login API ===")
try:
    r = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},
        timeout=10
    )
    print(f"Status: {r.status_code}")
    body = r.text[:500]
    print(f"Response: {body}")
    if r.status_code == 200:
        data = r.json()
        token = data.get("data", {}).get("access_token", "NONE")
        print(f"Token received: {token[:30]}...")
except Exception as e:
    print(f"Login ERROR: {e}")

print()
print("=== 3. Check Frontend ===")
try:
    r = requests.get("http://localhost:3000/login", timeout=5)
    ct = r.headers.get("content-type", "")
    print(f"Frontend: {r.status_code} (content-type: {ct})")
except Exception as e:
    print(f"Frontend DOWN: {e}")
