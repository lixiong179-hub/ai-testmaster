"""
一键启动 AI TestMaster 所有服务（后端 + 前端 + Celery）
启动顺序：Redis -> MySQL -> Celery Worker -> FastAPI -> Vue前端
"""
import os
import sys
import subprocess
import time
import socket
import threading
import locale


def setup_console_encoding():
    """在 Windows 下统一控制台和 Python 输出编码，避免中文日志乱码"""
    if os.name != "nt":
        return

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def build_subprocess_env():
    """统一子进程编码环境，保证 Python 子进程输出 UTF-8"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def get_subprocess_encoding():
    """获取子进程输出流的读取编码"""
    return "utf-8" if os.name == "nt" else locale.getpreferredencoding(False) or "utf-8"

def check_port(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def check_service(host, port, timeout=1):
    """检查服务是否可连接"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def kill_port_process(port):
    """杀死占用指定端口的进程"""
    print(f"  [检查] 端口 {port}...")
    if check_port(port):
        print(f"  [警告] 端口 {port} 被占用，尝试释放...")
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        print(f"  [操作] 终止进程 {pid}...")
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                        time.sleep(2)
                        break
        except Exception as e:
            print(f"  [错误] 释放端口失败: {e}")
    else:
        print(f"  [OK] 端口 {port} 可用")

def log_output(process, prefix):
    """实时输出进程日志"""
    for line in iter(process.stdout.readline, ""):
        if line:
            print(f"[{prefix}] {line.rstrip()}")


setup_console_encoding()
SUBPROCESS_ENV = build_subprocess_env()
SUBPROCESS_ENCODING = get_subprocess_encoding()

def wait_for_service(name, host, port, max_wait=30):
    """等待服务启动"""
    print(f"  [等待] {name} ({host}:{port})...", end="", flush=True)
    for i in range(max_wait):
        if check_service(host, port):
            print(f" [OK]")
            return True
        time.sleep(1)
        print(".", end="", flush=True)
    print(f" [超时]")
    return False

print("=" * 70)
print(" AI TestMaster 完整服务启动脚本")
print(" 启动顺序: Redis -> MySQL -> Celery -> FastAPI -> Vue")
print("=" * 70)

# 设置环境变量
os.environ["PYTHONPATH"] = "."

# ==================== 第1步：检查基础服务 ====================
print("\n>>> [1/5] 检查基础依赖服务...")
print("-" * 70)

# 检查 MySQL
print("  [检查] MySQL 数据库...")
from app.core.config import settings
if check_service("localhost", 3306):
    print("  [OK] MySQL 运行正常")
else:
    print("  [错误] MySQL 未启动！请先启动 MySQL 服务")
    print("         命令: net start mysql 或手动启动 MySQL")
    sys.exit(1)

# 检查 Redis
print("  [检查] Redis 服务...")
if check_service("localhost", 6379):
    print("  [OK] Redis 运行正常")
else:
    print("  [错误] Redis 未启动！请先启动 Redis 服务")
    print("         命令: redis-server 或手动启动 Redis")
    sys.exit(1)

# ==================== 第2步：清理端口 ====================
print("\n>>> [2/5] 清理应用端口...")
print("-" * 70)
kill_port_process(8000)  # FastAPI 端口
kill_port_process(3000)  # Vue 端口

# ==================== 第3步：启动 Celery Worker ====================
print("\n>>> [3/5] 启动 Celery Worker (异步任务队列)...")
print("-" * 70)
print("  [信息] Celery 用于执行测试任务，必须启动")

celery_process = subprocess.Popen(
    [sys.executable, "-m", "celery", "-A", "app.tasks.test_task", "worker", "--loglevel=info", "-P", "solo"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    text=True,
    encoding=SUBPROCESS_ENCODING,
    errors="replace",
    env=SUBPROCESS_ENV,
)

# 启动 Celery 日志线程
celery_log_thread = threading.Thread(target=log_output, args=(celery_process, "Celery"))
celery_log_thread.daemon = True
celery_log_thread.start()

# 等待 Celery 启动
time.sleep(3)

if celery_process.poll() is not None:
    print("  [错误] Celery 启动失败！")
    sys.exit(1)

print("  [OK] Celery Worker 已启动")

# ==================== 第4步：启动 FastAPI ====================
print("\n>>> [4/5] 启动 FastAPI 后端服务...")
print("-" * 70)
print("  地址: http://localhost:8000")
print("  API文档: http://localhost:8000/docs")

backend_process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    text=True,
    encoding=SUBPROCESS_ENCODING,
    errors="replace",
    env=SUBPROCESS_ENV,
)

# 启动后端日志线程
backend_log_thread = threading.Thread(target=log_output, args=(backend_process, "后端"))
backend_log_thread.daemon = True
backend_log_thread.start()

# 等待后端启动
time.sleep(3)

if backend_process.poll() is not None:
    print("  [错误] 后端启动失败！")
    celery_process.terminate()
    sys.exit(1)

print("  [OK] FastAPI 后端已启动")

# ==================== 第5步：启动 Vue 前端 ====================
print("\n>>> [5/5] 启动 Vue 前端服务...")
print("-" * 70)
print("  地址: http://localhost:3000")

# 在Windows上使用shell=True来找到npm命令
frontend_process = subprocess.Popen(
    "npm run dev",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=1,
    shell=True,
    text=True,
    encoding=SUBPROCESS_ENCODING,
    errors="replace",
    env=SUBPROCESS_ENV,
)

# 启动前端日志线程
frontend_log_thread = threading.Thread(target=log_output, args=(frontend_process, "前端"))
frontend_log_thread.daemon = True
frontend_log_thread.start()

# 等待前端启动
time.sleep(3)

if frontend_process.poll() is not None:
    print("  [错误] 前端启动失败！")
    backend_process.terminate()
    celery_process.terminate()
    sys.exit(1)

print("  [OK] Vue 前端已启动")

# ==================== 启动完成 ====================
print("\n" + "=" * 70)
print(" 所有服务启动完成！")
print("=" * 70)
print(" 前端地址:  http://localhost:3000")
print(" 后端地址:  http://localhost:8000")
print(" API文档:   http://localhost:8000/docs")
print("=" * 70)
print("\n[提示] 按 Ctrl+C 停止所有服务\n")

# 等待用户中断
try:
    while True:
        # 检查进程是否还在运行
        if celery_process.poll() is not None:
            print("\n[警告] Celery 服务已停止")
            break
        if backend_process.poll() is not None:
            print("\n[警告] 后端服务已停止")
            break
        if frontend_process.poll() is not None:
            print("\n[警告] 前端服务已停止")
            break
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n[操作] 正在停止所有服务...")
finally:
    print("[操作] 停止 Celery Worker...")
    celery_process.terminate()
    print("[操作] 停止 FastAPI 后端...")
    backend_process.terminate()
    print("[操作] 停止 Vue 前端...")
    frontend_process.terminate()
    
    # 等待进程结束
    try:
        celery_process.wait(timeout=5)
        backend_process.wait(timeout=5)
        frontend_process.wait(timeout=5)
    except:
        celery_process.kill()
        backend_process.kill()
        frontend_process.kill()
    
    print("[OK] 所有服务已停止")
