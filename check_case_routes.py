"""
Check all routes including ones starting with 'case'
"""
import requests

BASE_URL = "http://localhost:8000"

resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    print("All routes starting with /api/v1/case:")
    for path in sorted(paths.keys()):
        if "/case" in path.lower():
            print(f"  {path}")
            for method, info in paths[path].items():
                if method in ["get", "post", "put", "delete"]:
                    print(f"    {method.upper()}: {info.get('summary', 'N/A')}")

    print("\nAll routes starting with /api/v1/test-task:")
    for path in sorted(paths.keys()):
        if "test-task" in path.lower():
            print(f"  {path}")
            for method, info in paths[path].items():
                if method in ["get", "post", "put", "delete"]:
                    print(f"    {method.upper()}: {info.get('summary', 'N/A')}")
