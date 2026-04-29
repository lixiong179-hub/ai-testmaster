"""
测试登录请求
"""
import requests

BASE_URL = 'http://localhost:8000/api/v1/auth/login'

# 测试不同的密码
passwords = ['test1234', 'admin', 'admin123', 'password', 'password123']

for pwd in passwords:
    data = {'username': 'admin', 'password': pwd}
    resp = requests.post(BASE_URL, data=data)
    if resp.status_code == 200:
        print(f"PASSWORD FOUND: {pwd}")
        print("Response:", resp.text[:500])
        break
    else:
        print(f"Failed: {pwd} - {resp.status_code}")
