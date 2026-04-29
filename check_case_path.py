"""
Check all routes containing 'case' (not case_id)
"""
import requests

BASE_URL = "http://localhost:8000"

resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    print("All routes containing 'case' (lowercase):")
    for path in sorted(paths.keys()):
        if "/case/" in path.lower() or path.endswith("/case"):
            print(f"  {path}")
            for method, info in paths[path].items():
                if method in ["get", "post", "put", "delete"]:
                    print(f"    {method.upper()}: {info.get('summary', 'N/A')}")
