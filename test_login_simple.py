#!/usr/bin/env python3
"""
测试登录功能
"""
import requests

print("测试登录功能...")

# 测试登录
try:
    response = requests.post(
        'http://localhost:8000/api/v1/auth/login',
        json={'username': 'admin', 'password': 'password123'}
    )
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("登录成功！管理员账号已创建")
    else:
        print("登录失败，可能是管理员账号未创建")
except Exception as e:
    print(f"请求失败: {str(e)}")
