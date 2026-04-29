"""
安装所有依赖并运行FastAPI应用
"""
import os
import sys
import subprocess

print("=== AI TestMaster Setup and Run ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 安装所有必要的依赖
required_packages = [
    "fastapi==0.104.1",
    "uvicorn[standard]==0.24.0",
    "sqlalchemy==2.0.23",
    "pydantic==2.5.0",
    "pydantic-settings==2.1.0",
    "python-jose[cryptography]==3.3.0",
    "bcrypt==4.0.1",
    "passlib[bcrypt]==1.7.4"
]

print("Installing required packages...")
for package in required_packages:
    print(f"Installing: {package}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error installing {package}: {result.stderr}")
    else:
        print(f"Successfully installed {package}")

# 验证安装
print("\nVerifying installations...")
try:
    import fastapi
    print(f"FastAPI: {fastapi.__version__}")
except ImportError:
    print("Error: FastAPI not installed")

try:
    import uvicorn
    print(f"Uvicorn: {uvicorn.__version__}")
except ImportError:
    print("Error: Uvicorn not installed")

try:
    import sqlalchemy
    print(f"SQLAlchemy: {sqlalchemy.__version__}")
except ImportError:
    print("Error: SQLAlchemy not installed")

try:
    import pydantic
    print(f"Pydantic: {pydantic.__version__}")
except ImportError:
    print("Error: Pydantic not installed")

# 运行应用
print("\nStarting FastAPI application...")
print("Server will be available at: http://localhost:8000")
print("API documentation: http://localhost:8000/docs")
print("Press Ctrl+C to stop the server")
print("=" * 60)

# 直接运行app.main模块
subprocess.run([sys.executable, "-m", "app.main"])
