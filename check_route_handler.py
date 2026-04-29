"""
Check which route handles POST /api/v1/test-task
"""
import requests

BASE_URL = "http://localhost:8000"

# Login
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]

# Check OpenAPI for POST /api/v1/test-task
resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    post_info = paths.get("/api/v1/test-task", {}).get("post", {})
    print("POST /api/v1/test-task:")
    print(f"  Tags: {post_info.get('tags', [])}")
    print(f"  Summary: {post_info.get('summary', 'N/A')}")
    print(f"  Request Body: {post_info.get('requestBody', {})}")
    print()

    # Check which router this belongs to
    for path, methods in paths.items():
        if "post" in methods:
            if path == "/api/v1/test-task":
                print(f"Full route info: {methods['post']}")
