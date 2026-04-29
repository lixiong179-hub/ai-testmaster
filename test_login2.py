"""
测试后端登录
"""
import sys
import requests

# 直接使用 requests 测试登录
BASE_URL = 'http://localhost:8000'

print("Testing login endpoint...")
print("URL:", BASE_URL + "/api/v1/auth/login")
data = {'username': 'admin', 'password': 'test1234'}
print("Data:", data)

try:
    resp = requests.post(BASE_URL + "/api/v1/auth/login", data=data)
    print("Status:", resp.status_code)
    print("Headers:", dict(resp.headers))
    print("Body:", resp.text[:500])
except Exception as e:
    print("Error:", e)
