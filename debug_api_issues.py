import requests
import json

base = 'http://localhost:8000'

def get_token():
    r = requests.post(f'{base}/api/v1/auth/login', json={'username': 'admin', 'password': 'admin123'}, timeout=10)
    data = r.json()
    if 'data' in data and 'access_token' in data['data']:
        return data['data']['access_token']
    print(f"获取Token失败: {data}")
    return None

token = get_token()
if not token:
    print("无法获取Token，退出")
    exit(1)

headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

print(f"Token: {token[:30]}...")

print("\n1. 测试 auth/me (GET /api/v1/auth/me)")
r = requests.get(f'{base}/api/v1/auth/me', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n2. 测试 visibility/config (GET /api/visibility/config?level=global)")
r = requests.get(f'{base}/api/visibility/config', headers=headers, params={'level': 'global'})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n3. 测试 ui-prototype (GET /api/v1/ui-prototype/project/list/1)")
r = requests.get(f'{base}/api/v1/ui-prototype/project/list/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n4. 测试 execution/devices (GET /api/execution/devices)")
r = requests.get(f'{base}/api/execution/devices', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n5. 测试 quality/cases/1/quality (GET /api/v1/quality/cases/1/quality)")
r = requests.get(f'{base}/api/v1/quality/cases/1/quality', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n6. 测试 project/1 (GET /api/v1/project/1)")
r = requests.get(f'{base}/api/v1/project/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n7. 测试 test-point/detail/1 (GET /api/v1/test-point/detail/1)")
r = requests.get(f'{base}/api/v1/test-point/detail/1', headers=headers, params={'project_id': 1})
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")

print("\n8. 测试 test_data (GET /api/v1/test-data/1)")
r = requests.get(f'{base}/api/v1/test-data/1', headers=headers)
print(f"   状态码: {r.status_code}")
print(f"   响应: {r.text[:200]}")
