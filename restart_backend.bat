@echo off
cd /d "%~dp0"
echo Starting backend server...
start "Backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo Backend server started. Waiting...
timeout /t 5 /nobreak >nul
echo Done!
