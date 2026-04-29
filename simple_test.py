"""
简化版测试脚本
"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = 'http://localhost:8000'

print("="*60)
print("Step 1: Login (admin/test1234)")
print("="*60)

data = {'username': 'admin', 'password': 'test1234'}

try:
    resp = requests.post(f'{BASE_URL}/api/v1/auth/login', data=data)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")

    if resp.status_code == 200:
        result = resp.json()
        if 'data' in result and 'access_token' in result['data']:
            token = result['data']['access_token']
            print(f"\nSUCCESS! Token: {token[:50]}...")

            # 保存token
            with open('.test_token', 'w') as f:
                f.write(token)

            # 继续测试
            headers = {"Authorization": f"Bearer {token}"}

            print("\n" + "="*60)
            print("Step 2: Get Project List")
            print("="*60)
            resp2 = requests.get(f'{BASE_URL}/api/v1/project/list', headers=headers)
            print(f"Status: {resp2.status_code}")
            print(f"Response: {resp2.text[:500]}")
        else:
            print("No access_token in response")
    else:
        print("Login failed")

except Exception as e:
    print(f"Error: {e}")
