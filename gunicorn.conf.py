"""
Gunicorn生产环境配置文件
多进程+多线程模式，提高并发处理能力
"""
import multiprocessing
import os

# 服务器绑定地址
bind = "0.0.0.0:8000"

# 工作进程数
# 建议: 2 * CPU核心数 + 1
workers = multiprocessing.cpu_count() * 2 + 1

# 每个工作进程的线程数
threads = 4

# 工作进程类型
worker_class = "uvicorn.workers.UvicornWorker"

# 最大并发连接数
worker_connections = 1000

# 最大请求数（达到后重启工作进程，防止内存泄漏）
max_requests = 10000
max_requests_jitter = 1000

# 超时时间（秒）
timeout = 120
keepalive = 5

# 日志配置
accesslog = "-"  # 输出到stdout
errorlog = "-"   # 输出到stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "ai-testmaster"

# PID文件
pidfile = "/tmp/ai-testmaster.pid"

# 守护进程模式（后台运行）
daemon = False

# 预加载应用（节省内存）
preload_app = True

# 用户和组（生产环境建议设置）
# user = "www-data"
# group = "www-data"

# 安全限制
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 优雅重启超时
graceful_timeout = 30

# 工作进程启动超时
worker_timeout = 30


def on_starting(server):
    """服务器启动前执行"""
    print(f"Starting {proc_name} with {workers} workers...")


def on_reload(server):
    """配置重载时执行"""
    print(f"Reloading {proc_name} configuration...")


def worker_int(worker):
    """工作进程中断时执行"""
    print(f"Worker {worker.pid} received SIGINT or SIGQUIT")


def worker_abort(worker):
    """工作进程异常终止时执行"""
    print(f"Worker {worker.pid} aborted")
