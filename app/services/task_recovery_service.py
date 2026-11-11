"""任务恢复服务（R5-2）：孤儿 RUNNING 兜底扫描。

背景：`app/services/task_timeout_monitor.py` 已随 R4-5 删除，`test_tasks` 中
若进程崩溃/被 kill，任务会永久停留 `RUNNING`，造成：
    - 前端进度永远卡住；
    - R5-1 解耦后 executor 副本崩溃时无人收尾；
    - 报表统计把「中断」计成「执行中」。

本服务按 `settings.TASK_TIMEOUT_SECONDS` 扫描超时的 `RUNNING` 任务，
标记为 `FAILED` 并写 `end_time`，返回可审计的中断记录。

两种用法：
    1. 显式恢复：`TaskRecoveryService(db).scan_orphan_running()`（可同步立即收尾）
    2. 周期巡检：`start_task_recovery()`（在 `app/core/lifecycle.startup()` 注册，
       首轮在 `TIMEOUT_CHECK_INTERVAL` 秒后执行，避免与启动/持锁窗口重叠）

注意：`TIMEOUT_CHECK_INTERVAL <= 0` 时巡检不启动（灰度关闭用），
但启动即恢复仍可被显式调用。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.test_task import TaskStatus, TestTask
from app.utils.db_time import utcnow

INTERRUPTED_REASON = "marked_interrupted"

_monitor_task: Optional[asyncio.Task] = None


class TaskRecoveryService:
    """扫描并收尾孤儿 RUNNING 任务。"""

    def __init__(self, db: Session) -> None:
        """注入 sync 会话，禁止内部新建 Session。"""
        self._db = db

    def scan_orphan_running(
        self,
        *,
        now: Optional[datetime] = None,
        timeout_seconds: Optional[int] = None,
    ) -> list[dict]:
        """把超时的 RUNNING 任务标记为 FAILED。

        Args:
            now: 参照时间（默认当前 UTC）。
            timeout_seconds: 超时阈值（默认 `settings.TASK_TIMEOUT_SECONDS`）。

        Returns:
            list[dict]: 每条为 `{task_id, reason, stale_seconds, start_time}`。
        """
        reference = now or utcnow()
        timeout = (
            int(timeout_seconds)
            if timeout_seconds is not None
            else int(settings.TASK_TIMEOUT_SECONDS)
        )
        cutoff = reference - timedelta(seconds=max(timeout, 0))

        stale_tasks = (
            self._db.query(TestTask)
            .filter(
                TestTask.status == TaskStatus.RUNNING,
                (TestTask.start_time.is_(None)) | (TestTask.start_time < cutoff),
            )
            .all()
        )
        if not stale_tasks:
            return []

        recovered: list[dict] = []
        for task in stale_tasks:
            start_time = task.start_time
            stale_seconds = (
                int((reference - start_time).total_seconds())
                if start_time is not None
                else None
            )
            task.status = TaskStatus.FAILED
            task.error_message = (
                f"任务超时中断：已运行 {stale_seconds}s，超过阈值 {timeout}s"
                if stale_seconds is not None
                else f"任务缺少开始时间，判定为异常中断（阈值 {timeout}s）"
            )
            task.end_time = reference
            task.progress = min(task.progress or 0, 99)
            recovered.append(
                {
                    "task_id": task.id,
                    "reason": INTERRUPTED_REASON,
                    "stale_seconds": stale_seconds,
                    "start_time": start_time.isoformat() if start_time else None,
                }
            )
            logger.warning(
                f"孤儿 RUNNING 任务已标记中断: task_id={task.id} "
                f"stale={stale_seconds}s timeout={timeout}s"
            )

        self._db.commit()
        return recovered


def _scan_once() -> list[dict]:
    """独立会话执行一次扫描（后台线程调用）。"""
    from app.db.database import PrimarySessionLocal

    db = PrimarySessionLocal()
    try:
        return TaskRecoveryService(db).scan_orphan_running()
    finally:
        db.close()


async def _recovery_loop(interval_seconds: int) -> None:
    """周期巡检：每 interval 秒扫描一次（首轮先等待一个周期）。

    首轮先 `sleep` 而非立即扫描，避免与
    「应用刚启动 / 测试夹具持锁」的窗口重叠；需要立即收尾的场景
    请显式调用 `TaskRecoveryService(db).scan_orphan_running()`。
    """
    while True:
        await asyncio.sleep(max(interval_seconds, 1))
        try:
            recovered = await asyncio.to_thread(_scan_once)
            if recovered:
                logger.warning(f"任务恢复扫描完成: 收尾 {len(recovered)} 个孤儿任务")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("任务恢复扫描异常（将在下一轮重试）")


def start_task_recovery() -> None:
    """在事件循环内启动周期巡检（幂等；间隔 <=0 时关闭）。"""
    global _monitor_task

    interval = int(settings.TIMEOUT_CHECK_INTERVAL)
    if interval <= 0:
        logger.info("TIMEOUT_CHECK_INTERVAL<=0，孤儿任务巡检未启动（灰度关闭）")
        return
    if _monitor_task is not None and not _monitor_task.done():
        logger.debug("孤儿任务巡检已在运行，跳过重复启动")
        return

    try:
        _monitor_task = asyncio.get_running_loop().create_task(
            _recovery_loop(interval)
        )
    except RuntimeError:
        # 无运行中的事件循环（如脚本/测试直接调用）：退化为同步扫描一次
        recovered = _scan_once()
        logger.info(f"无事件循环，孤儿任务巡检降级为一次性扫描: {len(recovered)} 条")
        return

    logger.info(f"孤儿任务巡检已启动: interval={interval}s")


def shutdown_task_recovery() -> None:
    """停止周期巡检（幂等）。"""
    global _monitor_task

    if _monitor_task is None:
        return
    if not _monitor_task.done():
        _monitor_task.cancel()
        logger.info("孤儿任务巡检已停止")
    _monitor_task = None


__all__ = [
    "INTERRUPTED_REASON",
    "TaskRecoveryService",
    "shutdown_task_recovery",
    "start_task_recovery",
]
