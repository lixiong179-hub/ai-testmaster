"""
Check if there's a route override or additional route definition
"""
import requests

BASE_URL = "http://localhost:8000"

# Check OpenAPI components for CreateTestTask
resp = requests.get(f"{BASE_URL}/openapi.json")
if resp.status_code == 200:
    data = resp.json()
    schemas = data.get("components", {}).get("schemas", {})
    print("Available schemas:")
    for name in sorted(schemas.keys()):
        if "task" in name.lower():
            print(f"  {name}: {schemas[name]}")
