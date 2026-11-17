"""R5-1 阶段二：`POST /test_task/{id}/run` 在 worker 模式下改为「投递并返回 queued」。

验收：
    - `EXECUTOR_MODE=worker` → 任务置 PENDING（排队），响应 `executor_mode=worker`、
      `summary.status=queued`，不再在 Web 进程内执行
    - `EXECUTOR_MODE=inprocess`（默认）→ 走原执行路径（回归由既有测试覆盖）
"""
import uuid
from unittest.mock import patch

import pytest

from app.api.v1.endpoints import test_task_exec
from app.core.config import settings
from app.models.project import Project
from app.models.test_task import TaskStatus, TestTask


@pytest.fixture
def seed_task(db, testUser):
    """创建项目 + 待执行任务。"""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"worker_mode_{suffix}",
        user_id=testUser.id,
        description="worker 模式测试",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    task = TestTask(
        task_name=f"worker任务_{suffix}",
        project_id=project.id,
        case_ids=[1],
        executor_id=testUser.id,
        status=TaskStatus.PENDING,
        total_count=1,
        progress=0,
    )
    db.add(task)
    db.flush()
    return task


class TestWorkerModeEnqueue:
    async def test_worker_mode_enqueues_and_returns_queued(self, db, seed_task):
        """worker 模式：只入队，返回 queued，不执行。"""
        task = seed_task
        task.status = TaskStatus.COMPLETED
        db.flush()

        with patch.object(settings, "EXECUTOR_MODE", "worker"), patch.object(
            test_task_exec,
            "TestExecutionEngineV2",
        ) as engine_cls:
            resp = await test_task_exec.run_test_task(
                task_id=task.id, task=task, db=db
            )

        engine_cls.assert_not_called()
        assert resp["executor_mode"] == "worker"
        assert resp["summary"]["status"] == "queued"
        assert resp["summary"]["task_id"] == task.id
        assert resp["task"]["status"] == TaskStatus.PENDING
        assert resp["task"]["status_label"] == "排队中"

        db.expire_all()
        refreshed = db.query(TestTask).filter(TestTask.id == task.id).first()
        assert refreshed.status == TaskStatus.PENDING
        assert refreshed.start_time is None

    async def test_worker_mode_rejects_running_task(self, db, seed_task):
        """worker 模式：正在执行的任务重复触发 → 409。"""
        from fastapi import HTTPException

        task = seed_task
        task.status = TaskStatus.RUNNING
        db.flush()

        with patch.object(settings, "EXECUTOR_MODE", "worker"), pytest.raises(HTTPException) as exc:
            await test_task_exec.run_test_task(task_id=task.id, task=task, db=db)

        assert exc.value.status_code == 409

    def test_default_mode_is_inprocess(self):
        """默认部署形态保持 inprocess（部署级兜底开关）。"""
        assert settings.EXECUTOR_MODE == "inprocess"
