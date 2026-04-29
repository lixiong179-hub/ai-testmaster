"""
启动FastAPI服务器并保持运行
"""
import os
import sys
import subprocess
import time

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== AI TestMaster Server Starter ===")
print(f"Python executable: {sys.executable}")
print(f"Current directory: {os.getcwd()}")

# 检查端口是否被占用
def check_port(port):
    """检查端口是否被占用"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

# 杀死占用端口的进程
def kill_port_process(port):
    """杀死占用指定端口的进程"""
    if os.name == "nt":
        # Windows系统
        try:
            subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            result = subprocess.run(
                ["netstat", "-ano"], 
                capture_output=True, 
                text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    pid = line.split()[-1]
                    print(f"Killing process {pid} on port {port}")
                    subprocess.run(["taskkill", "/F", "/PID", pid])
                    time.sleep(2)
        except Exception as e:
            print(f"Error killing process: {e}")

# 检查并清理端口
PORT = 8000
if check_port(PORT):
    print(f"Port {PORT} is in use, trying to free it...")
    kill_port_process(PORT)

# 安装依赖
print("Checking dependencies...")
try:
    import fastapi
    import uvicorn
    print(f"FastAPI: {fastapi.__version__}")
    print(f"Uvicorn: {uvicorn.__version__}")
except ImportError:
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], check=True)

# 启动服务器
print("Starting FastAPI server...")
print(f"Server will be available at: http://localhost:{PORT}")
print(f"API documentation: http://localhost:{PORT}/docs")
print("Press Ctrl+C to stop the server")
print("=" * 60)

# 直接运行app.main模块
subprocess.run([sys.executable, "-m", "app.main"])
