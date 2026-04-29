"""强制重启服务器"""
import subprocess
import time
import requests
import sys
import os

# 切换到项目目录
os.chdir(r"c:\Users\Administrator\Desktop\ai-testmaster(2)\ai-testmaster")

# 杀死现有进程
print("杀死现有python进程...")
subprocess.run('taskkill /F /IM python.exe', shell=True, capture_output=True)
time.sleep(3)

# 启动新服务器
print("启动服务器...")
proc = subprocess.Popen(
    'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000',
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)

# 等待服务器启动
print("等待服务器启动...")
for i in range(20):
    try:
        r = requests.get('http://localhost:8000/', timeout=1)
        if r.status_code == 200:
            print("服务器启动成功!")
            break
    except:
        pass
    time.sleep(1)
else:
    print("服务器启动超时!")
    sys.exit(1)

# 等待额外时间确保完全加载
time.sleep(3)

# 检查端点
r = requests.get('http://localhost:8000/openapi.json')
endpoints = r.json()['paths']

print("\n项目相关端点:")
for p in endpoints:
    if 'project' in p.lower():
        methods = list(endpoints[p].keys())
        print(f"  {p}: {methods}")

print("\n包含config的项目端点:")
for p in endpoints:
    if 'config' in p.lower() and 'project' in p.lower():
        print(f"  {p}")

print("\n所有PUT端点:")
for p in endpoints:
    if 'put' in endpoints[p]:
        print(f"  PUT {p}")

print("\n测试完成!")
