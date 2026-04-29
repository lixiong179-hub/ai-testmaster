@echo off
setlocal

echo === AI TestMaster Server Start (Skip DB) ===

rem 设置跳过数据库初始化
set SKIP_DB_INIT=true

rem 检查Python版本
echo Checking Python version...
python --version

rem 启动服务
echo Starting FastAPI server (without database initialization)...
echo Server will be available at: http://localhost:8000
echo API documentation: http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo ===============================

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

endlocal
