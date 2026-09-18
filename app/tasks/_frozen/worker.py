"""Worker 启动配置（Phase 1 Task 3：分布式测试执行引擎）

业务用途：Celery Worker 与 Beat 启动入口，供 Docker/K8s 容器启动命令调用。
设计原则：
1. Worker 使用 gevent 池提升 IO 并发；
2. Beat 独立部署，单实例运行避免周期任务重复执行；
3. 优雅终止：warm_shutdown 等待在途任务完成。

启动命令：
    # Worker
    celery -A app.tasks.celery_app:celery_app worker -Q test_execution,scheduler \
        --concurrency=4 --pool=gevent --loglevel=INFO

    # Beat
    celery -A app.tasks.celery_app:celery_app beat --loglevel=INFO

    # 进程内启动（开发环境）
    python -m app.tasks.worker start_worker
    python -m app.tasks.worker start_beat
"""
import logging
import sys

from app.tasks.celery_app import get_celery_app
from app.tasks.scheduler import get_beat_schedule

logger = logging.getLogger(__name__)

celery_app = get_celery_app()
celery_app.conf.beat_schedule = get_beat_schedule()


def start_worker(concurrency: int = 4, pool: str = "gevent", loglevel: str = "INFO") -> None:
    """启动 Celery Worker。

    业务用途：消费 test_execution 与 scheduler 队列，执行分布式任务。
    边界场景：Redis 不可用时启动失败，K8s readinessProbe 检测后重启 Pod。
    """
    from celery.bin.worker import worker as worker_cmd

    argv = [
        "worker",
        "--loglevel", loglevel,
        "--concurrency", str(concurrency),
        "--pool", pool,
        "-Q", "test_execution,scheduler",
        "--hostname", "worker@%h",
    ]
    cmd = worker_cmd(app=celery_app)
    cmd.execute_from_commandline(argv)


def start_beat(loglevel: str = "INFO") -> None:
    """启动 Celery Beat 调度器。

    业务用途：周期性触发 pipeline_timeout_check 等任务。
    边界场景：Beat 单实例运行，多实例部署时需配置分布式锁避免重复触发。
    """
    from celery.bin.beat import beat as beat_cmd

    argv = [
        "beat",
        "--loglevel", loglevel,
        "--schedule", "/tmp/celerybeat-schedule",
        "--pidfile", "/tmp/celerybeat.pid",
    ]
    cmd = beat_cmd(app=celery_app)
    cmd.execute_from_commandline(argv)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m app.tasks.worker <start_worker|start_beat>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "start_worker":
        start_worker()
    elif cmd == "start_beat":
        start_beat()
    else:
        print(f"未知命令: {cmd}，支持: start_worker, start_beat")
        sys.exit(1)
