"""生产环境启动脚本

根据 CPU 核数自动计算 Worker 数量，以多进程模式启动 Uvicorn。
Worker 数量 = min(CPU核数 * 2 + 1, 8)
生产环境不启用 --reload 热重载。
"""
import os
import sys
import multiprocessing


def main() -> None:
    # Workers 数量：CPU 核数 * 2 + 1，但不超过 8
    cpu_count = multiprocessing.cpu_count()
    workers = min(cpu_count * 2 + 1, 8)

    # 后端启动
    os.execvp(
        sys.executable,
        [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--workers", str(workers),
            # 注意：无 --reload
        ],
    )


if __name__ == "__main__":
    main()
