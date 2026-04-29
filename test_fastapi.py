"""
测试FastAPI安装和运行
"""
import os
import sys

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 尝试导入fastapi
try:
    import fastapi
    print(f"FastAPI is installed: {fastapi.__version__}")
except ImportError:
    print("FastAPI not installed, installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], check=True)
    import fastapi
    print(f"FastAPI installed: {fastapi.__version__}")

# 测试运行应用
print("Starting FastAPI application...")
import subprocess
subprocess.run([sys.executable, "app/main.py"])
