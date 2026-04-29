"""
测试登录
"""
import requests
import time

time.sleep(3)

print("=== Testing Login ===")
resp = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    data={'username': 'admin', 'password': 'password123'}
)
print("Status:", resp.status_code)
print("Response:", resp.text[:500])
