"""
Debug - Check the actual route from backend
"""
import requests

BASE_URL = "http://localhost:8000"

resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    # Find all routes with test-task or test_task
    for path in sorted(paths.keys()):
        if "test-task" in path.lower() or "test_task" in path.lower():
            print(f"Path: {path}")
            for method, info in paths[path].items():
                if method in ["get", "post", "put", "delete"]:
                    print(f"  {method.upper()}: {info.get('operationId', 'N/A')}")
