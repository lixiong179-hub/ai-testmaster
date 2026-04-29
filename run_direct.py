"""
直接运行FastAPI应用，不使用subprocess
"""
import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== Direct FastAPI Runner ===")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 检查依赖
try:
    import fastapi
    import uvicorn
    print(f"FastAPI: {fastapi.__version__}")
    print(f"Uvicorn: {uvicorn.__version__}")
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Installing dependencies...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn"], check=True)

# 导入应用
try:
    from app.main import app
    print("App imported successfully")
except ImportError as e:
    print(f"Error importing app: {e}")
    sys.exit(1)

# 运行应用
print("Starting FastAPI server...")
print("Server will be available at: http://localhost:8000")
print("API documentation: http://localhost:8000/docs")
print("Press Ctrl+C to stop the server")
print("=" * 60)

# 直接运行uvicorn
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
