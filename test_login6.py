"""
直接用 requests 测试登录
"""
import requests

BASE_URL = 'http://localhost:8000'

# 测试登录
print("=== Login Test ===")
resp = requests.post(
    f'{BASE_URL}/api/v1/auth/login',
    data={'username': 'admin', 'password': 'password123'}
)
print("Status:", resp.status_code)
print("Response:", resp.text[:500])
