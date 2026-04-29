"""
测试登录请求
"""
import requests

BASE_URL = 'http://localhost:8000/api/v1/auth/login'

data = {'username': 'admin', 'password': 'test1234'}
resp = requests.post(BASE_URL, data=data)
print("Status:", resp.status_code)
print("Response:", resp.text[:500])
