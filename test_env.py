"""
测试Python环境和模块导入
"""
import sys
import os

print("Python version:", sys.version)
print("Python executable:", sys.executable)
print("Current directory:", os.getcwd())
print("Python path:", sys.path)

# 尝试导入fastapi
try:
    import fastapi
    print("FastAPI version:", fastapi.__version__)
except ImportError as e:
    print("FastAPI not found:", e)

# 尝试导入uvicorn
try:
    import uvicorn
    print("Uvicorn version:", uvicorn.__version__)
except ImportError as e:
    print("Uvicorn not found:", e)
