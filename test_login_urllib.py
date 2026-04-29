#!/usr/bin/env python3
"""
测试登录功能
"""
import urllib.request
import urllib.parse
import json

print("测试登录功能...")

# 测试登录
try:
    url = 'http://localhost:8000/api/v1/auth/login'
    data = {'username': 'admin', 'password': 'password123'}
    data_json = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=data_json, headers={'Content-Type': 'application/json'})
    response = urllib.request.urlopen(req)
    
    status_code = response.getcode()
    response_data = json.loads(response.read().decode('utf-8'))
    
    print(f"Status code: {status_code}")
    print(f"Response: {response_data}")
    
    if status_code == 200:
        print("登录成功！管理员账号已创建")
    else:
        print("登录失败，可能是管理员账号未创建")
except Exception as e:
    print(f"请求失败: {str(e)}")
