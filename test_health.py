#!/usr/bin/env python3
"""
测试应用健康检查端点
"""
import urllib.request
import json

print("测试应用健康检查端点...")

try:
    url = 'http://localhost:8000/health'
    response = urllib.request.urlopen(url)
    
    status_code = response.getcode()
    response_data = json.loads(response.read().decode('utf-8'))
    
    print(f"Status code: {status_code}")
    print(f"Response: {response_data}")
    
    if status_code == 200:
        print("应用启动成功！")
    else:
        print("应用启动失败")
except Exception as e:
    print(f"请求失败: {str(e)}")
