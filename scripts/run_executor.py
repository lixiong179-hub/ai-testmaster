"""独立执行进程入口（R5-1 阶段二）。

从 `test_tasks` 队列领取 PENDING 任务并在**独立进程/容器**内执行，
使长任务不再占用 Web 进程（API 延迟不受执行影响）。

用法：
    python scripts/run_executor.py                 # 常驻轮询
    python scripts/run_executor.py --once          # 领取并执行 1 个任务后退出
    python scripts/run_executor.py --max-tasks 5   # 执行 5 个任务后退出

环境变量：
    EXECUTOR_POLL_INTERVAL_SECONDS  空闲轮询间隔（默认 1.0）
    EXECUTOR_SCAN_LIMIT             单次扫描候选上限（默认 10）

部署：`docker compose up -d --scale executor=3`（见 docker-compose.yml 的 `executor` 服务）。
退出码：0 = 正常退出（含队列为空且 `--once`）；1 = 执行异常且未恢复。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

from app.core.config import settings  # noqa: E402


def _execute(task_id: int, *, dry_run: bool = False) -> bool:
    """领取后执行单个任务，返回是否成功（不抛出）。

    Args:
        task_id: 已领取的任务 ID。
        dry_run: 只走「领取 → 完成」状态机，不启动浏览器/执行用例
            （用于隔离性冒烟与多副本互斥验证）。
    """
    from app.db.database import PrimarySessionLocal
    from app.services.execution_dispatcher import ExecutionDispatcher
    from app.services.test_execution_engine_v2 import TestExecutionEngineV2

    db = PrimarySessionLocal()
    try:
        if dry_run:
            ExecutionDispatcher(db).mark_completed(task_id)
            logger.info(f"dry-run 任务完成: task_id={task_id}")
            return True

        engine = TestExecutionEngineV2(db)
        try:
            asyncio.run(engine.execute_test_task(task_id))
            logger.info(f"任务执行完成: task_id={task_id}")
            return True
        except Exception as exc:  # 任务级异常：标记失败后继续领取下一个
            logger.exception(f"任务执行异常: task_id={task_id}")
            try:
                ExecutionDispatcher(db).mark_failed(task_id, str(exc))
            except Exception:
                logger.exception(f"标记任务失败时异常: task_id={task_id}")
            return False
    finally:
        db.close()


def _claim() -> int | None:
    """领取一个排队任务（独立短会话，尽快释放连接）。"""
    from app.db.database import PrimarySessionLocal
    from app.services.execution_dispatcher import ExecutionDispatcher

    db = PrimarySessionLocal()
    try:
        return ExecutionDispatcher(db).claim_next(scan_limit=settings.EXECUTOR_SCAN_LIMIT)
    finally:
        db.close()


def run(*, once: bool = False, max_tasks: int = 0, dry_run: bool = False) -> int:
    """主循环：领取 → 执行 → 休眠。

    Args:
        once: 只尝试领取并执行一个任务后退出。
        max_tasks: 执行多少个任务后退出（0 表示不限）。
        dry_run: 只推进状态机（领取 → 完成），不执行真实用例。

    Returns:
        int: 进程退出码。
    """
    poll_interval = max(float(settings.EXECUTOR_POLL_INTERVAL_SECONDS), 0.1)
    executed = 0
    failures = 0
    logger.info(
        f"executor 启动 | mode={settings.EXECUTOR_MODE} dry_run={dry_run} "
        f"poll={poll_interval}s scan_limit={settings.EXECUTOR_SCAN_LIMIT}"
    )

    while True:
        task_id = _claim()
        if task_id is None:
            if once:
                logger.info("队列为空，executor 退出（--once）")
                return 0
            time.sleep(poll_interval)
            continue

        ok = _execute(task_id, dry_run=dry_run)
        executed += 1
        failures += 0 if ok else 1

        if once or (max_tasks and executed >= max_tasks):
            logger.info(f"executor 退出 | executed={executed} failures={failures}")
            return 0 if failures == 0 else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="R5-1 独立执行进程")
    parser.add_argument("--once", action="store_true", help="只处理 1 个任务后退出")
    parser.add_argument("--max-tasks", type=int, default=0, help="处理 N 个任务后退出")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只推进状态机（领取 → 完成），不执行真实用例（隔离性冒烟用）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return run(once=args.once, max_tasks=args.max_tasks, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logger.info("executor 收到中断信号，退出")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
