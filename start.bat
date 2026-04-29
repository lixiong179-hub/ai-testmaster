@echo off
echo === AI TestMaster Server Start ===

rem 检查Python版本
echo Checking Python version...
python --version

rem 安装依赖
echo Installing dependencies...
python -m pip install fastapi uvicorn sqlalchemy pydantic-settings bcrypt python-jose passlib

rem 检查安装
echo Verifying installation...
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import uvicorn; print('Uvicorn:', uvicorn.__version__)"

rem 启动服务
echo Starting FastAPI server...
echo Server will be available at: http://localhost:8000
echo API documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo ===============================
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
