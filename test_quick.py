"""
测试后端
"""
import requests

BASE_URL = 'http://localhost:8000'

# 测试登录
resp = requests.post(
    f'{BASE_URL}/api/v1/auth/login',
    data={'username': 'admin', 'password': 'password123'}
)
if resp.status_code == 200:
    token = resp.json()['data']['access_token']
    headers = {"Authorization": f"Bearer {token}"}
    # 测试获取项目列表
    resp = requests.get(f'{BASE_URL}/api/v1/project/list', headers=headers)
    print("Projects:", resp.status_code)
else:
    print("Login failed:", resp.status_code)
