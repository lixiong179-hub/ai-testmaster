"""
修复Python路径并运行FastAPI应用
"""
import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path[:5]}")

# 尝试导入fastapi
try:
    import fastapi
    print(f"FastAPI version: {fastapi.__version__}")
except ImportError:
    print("FastAPI not installed, installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], check=True)
    import fastapi
    print(f"FastAPI installed: {fastapi.__version__}")

# 测试导入app模块
try:
    from app.core.config import settings
    print(f"App module imported successfully. App name: {settings.APP_NAME}")
except ImportError as e:
    print(f"Error importing app module: {e}")
    print("Checking directory structure...")
    import subprocess
    subprocess.run(["dir" if os.name == "nt" else "ls", "-la"], cwd=os.getcwd())
    exit(1)

# 运行应用
print("Starting FastAPI application...")
import subprocess
subprocess.run([sys.executable, "-m", "app.main"])
