"""
测试登录请求
"""
import requests

BASE_URL = 'http://localhost:8000/api/v1/auth/login'

# 测试 password123
data = {'username': 'admin', 'password': 'password123'}
resp = requests.post(BASE_URL, data=data)
print("Status:", resp.status_code)
print("Response:", resp.text[:500])
