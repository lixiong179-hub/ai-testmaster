"""
Check the actual route handler
"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Login
data = {"username": "admin", "password": "password123"}
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", data=data)
token = resp.json()["data"]["access_token"]

# Check the OpenAPI spec for this endpoint
resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    # Get the CreateTestTaskRequest schema
    create_task_info = paths.get("/api/v1/test-task", {}).get("post", {})

    # Get the parameters
    params = create_task_info.get("parameters", [])
    print("Parameters:")
    for p in params:
        print(f"  {p['name']} ({p['in']}): required={p.get('required', False)}, schema={p.get('schema', {})}")

    # Get the requestBody schema
    rb = create_task_info.get("requestBody", {})
    content = rb.get("content", {}).get("application/json", {})
    schema = content.get("schema", {})
    print(f"\nRequest body schema: {json.dumps(schema, indent=2)}")
