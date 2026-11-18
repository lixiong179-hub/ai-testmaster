"""执行任务投递层（R5-1 阶段二）。

把「执行」从 Web 进程中解耦：Web 侧只负责**入队**并立即返回 `queued`，
独立 `executor` 容器负责**领取并执行**。队列语义复用 `test_tasks.status`：

    PENDING(0)  → 排队中，可被任意 executor 领取
    RUNNING(1)  → 已被某个 executor 领取

设计要点：
    1. **原子领取**：`UPDATE ... WHERE id=:id AND status=PENDING`，
       以 `rowcount` 判定归属，避免多副本重复执行（无需新增列/迁移）。
    2. **无状态**：`ExecutionDispatcher` 只持有一个 sync Session，可被
       Web 进程（`asyncio.to_thread`）与 executor 进程直接复用。
    3. **可回滚**：`settings.EXECUTOR_MODE` 为 `inprocess` 时 Web 侧仍走
       原有「同步执行」路径，本模块完全不参与，作为部署级兜底开关。
"""

from __future__ import annotations


from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.test_task import TaskStatus, TestTask
from app.utils.db_time import utcnow

QUEUED_LABEL = "排队中"


class ExecutionDispatcher:
    """测试任务入队与原子领取。"""

    def __init__(self, db: Session) -> None:
        """注入 sync 会话，禁止内部新建 Session。"""
        self._db = db

    def enqueue(self, task_id: int) -> dict:
        """把任务置为排队态（PENDING），等待 executor 领取。

        Args:
            task_id: 测试任务 ID。

        Returns:
            dict: `{task_id, status, status_label, queued_at}`。

        Raises:
            ValueError: 任务不存在，或任务正在执行（不允许重复入队）。
        """
        task = self._db.query(TestTask).filter(TestTask.id == task_id).first()
        if task is None:
            raise ValueError(f"测试任务不存在: {task_id}")
        if task.status == TaskStatus.RUNNING:
            raise ValueError(f"任务正在执行，不可重复入队: {task_id}")

        self._db.execute(
            update(TestTask)
            .where(TestTask.id == task_id)
            .values(
                status=TaskStatus.PENDING,
                progress=0,
                success_count=0,
                fail_count=0,
                start_time=None,
                end_time=None,
                error_message=None,
            )
        )
        self._db.commit()
        logger.info(f"任务已入队: task_id={task_id} status=PENDING")
        return {
            "task_id": task_id,
            "status": TaskStatus.PENDING,
            "status_label": QUEUED_LABEL,
            "queued_at": utcnow().isoformat(),
        }

    def claim_next(self, *, scan_limit: int = 10, task_id: int | None = None) -> int | None:
        """领取一个排队任务并置为 RUNNING。

        通过「条件更新 + rowcount」实现原子占用：同一任务被多个 executor
        同时扫描到时，只有一个副本的 `UPDATE` 命中，其余返回 0 行。

        Args:
            scan_limit: 单次最多尝试的候选任务数（避免长事务）。
            task_id: 指定任务 ID 时只尝试该任务（定向投递/测试用）。

        Returns:
            Optional[int]: 领取成功的任务 ID；无任务时返回 None。
        """
        query = select(TestTask.id).where(TestTask.status == TaskStatus.PENDING)
        if task_id is not None:
            query = query.where(TestTask.id == task_id)
        candidates = self._db.execute(query.order_by(TestTask.id.asc()).limit(max(scan_limit, 1))).scalars().all()

        for task_id in candidates:
            result = self._db.execute(
                update(TestTask)
                .where(
                    TestTask.id == task_id,
                    TestTask.status == TaskStatus.PENDING,
                )
                .values(
                    status=TaskStatus.RUNNING,
                    start_time=utcnow(),
                    error_message=None,
                )
            )
            if result.rowcount:
                self._db.commit()
                logger.info(f"任务已领取: task_id={task_id} status=RUNNING")
                return task_id
            self._db.rollback()
            logger.debug(f"任务领取竞争失败，跳过: task_id={task_id}")

        return None

    def mark_completed(self, task_id: int) -> None:
        """把任务标记为完成（executor `--dry-run` 冒烟用，不执行真实用例）。"""
        self._db.execute(
            update(TestTask)
            .where(TestTask.id == task_id)
            .values(
                status=TaskStatus.COMPLETED,
                progress=100,
                end_time=utcnow(),
                error_message=None,
            )
        )
        self._db.commit()
        logger.info(f"任务标记完成（dry-run）: task_id={task_id}")

    def mark_failed(self, task_id: int, error: str) -> None:
        """把任务标记为失败（executor 侧执行异常兜底）。"""
        self._db.execute(
            update(TestTask)
            .where(TestTask.id == task_id)
            .values(
                status=TaskStatus.FAILED,
                end_time=utcnow(),
                error_message=error[:2000],
            )
        )
        self._db.commit()
        logger.error(f"任务执行异常已标记失败: task_id={task_id} error={error[:200]}")


__all__ = ["ExecutionDispatcher", "QUEUED_LABEL"]
