"""
Check all routes
"""
import requests

BASE_URL = "http://localhost:8000"

resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    paths = data.get("paths", {})

    print("All routes in the API:")
    for path in sorted(paths.keys()):
        methods = list(paths[path].keys())
        print(f"  {path}: {methods}")
