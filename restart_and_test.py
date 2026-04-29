"""
重启后端并测试
"""
import subprocess
import time

# 杀掉旧进程
subprocess.run(['taskkill', '/F', '/PID', '15712'], capture_output=True)
time.sleep(2)

# 启动新进程
print("Starting backend with reload...")
proc = subprocess.Popen(
    ['python', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'],
    cwd=r'c:\Users\Administrator\Desktop\ai-testmaster(2)\ai-testmaster'
)

print("Waiting for backend to start...")
time.sleep(5)

# 测试
import requests

resp = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    data={'username': 'admin', 'password': 'password123'}
)
print(f"Login: {resp.status_code}")
if resp.status_code == 200:
    token = resp.json()['data']['access_token']
    headers = {"Authorization": f"Bearer {token}"}

    # 测试 AI 生成
    resp = requests.post(
        'http://localhost:8000/api/v1/test-case/ai-generate',
        json={
            "project_id": 3,
            "description": "Test user login: validate username and password fields, check error handling"
        },
        headers=headers,
        timeout=120
    )
    print(f"AI Generate: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")
