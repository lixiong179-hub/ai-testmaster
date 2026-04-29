"""
安装依赖并运行FastAPI应用
"""
import subprocess
import sys

print("Python version:", sys.version)
print("Installing fastapi and uvicorn...")

# 安装依赖
subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], check=True)

print("Verifying installation...")
subprocess.run([sys.executable, "-c", "import fastapi; print('FastAPI version:', fastapi.__version__)"])
subprocess.run([sys.executable, "-c", "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"])

print("Starting application...")
subprocess.run([sys.executable, "app/main.py"])
