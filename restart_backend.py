"""
重启后端
"""
import subprocess
import os

# 杀掉 8000 端口的进程
result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if ':8000' in line and 'LISTENING' in line:
        pid = line.split()[-1]
        print(f"Killing PID: {pid}")
        subprocess.run(['taskkill', '/F', '/PID', pid])
        break

print("Restarting backend...")

# 启动后端
os.chdir(r'c:\Users\Administrator\Desktop\ai-testmaster(2)\ai-testmaster')
subprocess.Popen(['python', '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'])

print("Backend restarting...")
