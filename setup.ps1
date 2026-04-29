# 设置执行策略
Set-ExecutionPolicy Bypass -Scope Process -Force

Write-Host "=== AI TestMaster Setup ==="

# 获取当前目录
$currentDir = Get-Location
Write-Host "Current directory: $currentDir"

# 检查Python版本
Write-Host "Checking Python version..."
python --version

# 安装FastAPI和Uvicorn
Write-Host "Installing FastAPI and Uvicorn..."
python -m pip install fastapi uvicorn

# 验证安装
Write-Host "Verifying installation..."
try {
    python -c "import fastapi; print('FastAPI version:', fastapi.__version__)"
    python -c "import uvicorn; print('Uvicorn version:', uvicorn.__version__)"
    Write-Host "Installation successful!"
} catch {
    Write-Host "Installation failed: $($_.Exception.Message)"
    exit 1
}

# 启动应用
Write-Host "Starting FastAPI application..."
python app/main.py
