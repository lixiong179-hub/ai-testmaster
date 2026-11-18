"""R5-2 重启恢复验收：孤儿 RUNNING 任务必须被收尾。

验收口径：
    - 超时 RUNNING → `FAILED` + `end_time`，reason = `marked_interrupted`
    - 未超时 RUNNING → 不动
    - 恢复幂等：第二次扫描返回空
    - 「重启后无裸 RUNNING」：恢复后该项目的 RUNNING 计数为 0
    - `TIMEOUT_CHECK_INTERVAL<=0` 时不启动巡检（灰度关闭）
"""

import asyncio
import uuid
from datetime import timedelta

import pytest

from app.core.config import settings
from app.models.project import Project
from app.models.test_task import TaskStatus, TestTask
from app.services import task_recovery_service
from app.services.task_recovery_service import (
    INTERRUPTED_REASON,
    TaskRecoveryService,
)
from app.utils.db_time import utcnow


@pytest.fixture
def recovery_task(db, testUser):
    """创建一个超时的 RUNNING 任务与一个新鲜的 RUNNING 任务。"""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"resume_{suffix}",
        user_id=testUser.id,
        description="重启恢复测试",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    timeout = int(settings.TASK_TIMEOUT_SECONDS)
    stale = TestTask(
        task_name=f"孤儿任务_{suffix}",
        project_id=project.id,
        case_ids=[1],
        executor_id=testUser.id,
        status=TaskStatus.RUNNING,
        total_count=1,
        progress=40,
        start_time=utcnow() - timedelta(seconds=timeout + 120),
    )
    fresh = TestTask(
        task_name=f"在跑任务_{suffix}",
        project_id=project.id,
        case_ids=[2],
        executor_id=testUser.id,
        status=TaskStatus.RUNNING,
        total_count=1,
        progress=10,
        start_time=utcnow() - timedelta(seconds=5),
    )
    db.add_all([stale, fresh])
    db.flush()
    return {"project": project, "stale": stale, "fresh": fresh}


def _running_count(db, project_id: int) -> int:
    db.expire_all()
    return (
        db.query(TestTask)
        .filter(
            TestTask.project_id == project_id,
            TestTask.status == TaskStatus.RUNNING,
        )
        .count()
    )


class TestOrphanRecovery:
    def test_stale_running_marked_interrupted(self, db, recovery_task):
        """超时 RUNNING → FAILED，reason=marked_interrupted，写 end_time。"""
        recovered = TaskRecoveryService(db).scan_orphan_running()

        stale_entry = next(item for item in recovered if item["task_id"] == recovery_task["stale"].id)
        assert stale_entry["reason"] == INTERRUPTED_REASON
        assert stale_entry["stale_seconds"] >= int(settings.TASK_TIMEOUT_SECONDS)

        db.expire_all()
        stale = db.query(TestTask).filter(TestTask.id == recovery_task["stale"].id).first()
        assert stale.status == TaskStatus.FAILED
        assert stale.end_time is not None

    def test_fresh_running_untouched(self, db, recovery_task):
        """未超时的 RUNNING 任务不参与恢复。"""
        recovered = TaskRecoveryService(db).scan_orphan_running()

        assert all(item["task_id"] != recovery_task["fresh"].id for item in recovered)
        db.expire_all()
        fresh = db.query(TestTask).filter(TestTask.id == recovery_task["fresh"].id).first()
        assert fresh.status == TaskStatus.RUNNING

    def test_no_bare_running_after_recovery(self, db, recovery_task):
        """「重启后无裸 RUNNING」：恢复后仅剩仍在时限内的任务。"""
        TaskRecoveryService(db).scan_orphan_running()

        assert _running_count(db, recovery_task["project"].id) == 1
        db.expire_all()
        remaining = (
            db.query(TestTask)
            .filter(
                TestTask.project_id == recovery_task["project"].id,
                TestTask.status == TaskStatus.RUNNING,
            )
            .first()
        )
        assert remaining.id == recovery_task["fresh"].id

    def test_recovery_is_idempotent(self, db, recovery_task):
        """恢复幂等：第二次扫描不再返回已收尾任务。"""
        service = TaskRecoveryService(db)
        first = service.scan_orphan_running()
        second = service.scan_orphan_running()

        assert any(item["task_id"] == recovery_task["stale"].id for item in first)
        assert all(item["task_id"] != recovery_task["stale"].id for item in second)

    def test_custom_timeout_threshold(self, db, recovery_task):
        """显式传入更小阈值时，fresh 任务也会被判为孤儿（阈值可配）。"""
        recovered = TaskRecoveryService(db).scan_orphan_running(timeout_seconds=0)

        ids = {item["task_id"] for item in recovered}
        assert recovery_task["stale"].id in ids
        assert recovery_task["fresh"].id in ids


class TestRecoveryLifecycle:
    def test_start_is_noop_when_interval_disabled(self, monkeypatch):
        """TIMEOUT_CHECK_INTERVAL<=0 → 不启动巡检（灰度关闭）。"""
        monkeypatch.setattr(settings, "TIMEOUT_CHECK_INTERVAL", 0)
        task_recovery_service._monitor_task = None

        task_recovery_service.start_task_recovery()

        assert task_recovery_service._monitor_task is None

    async def test_start_and_shutdown_in_event_loop(self, monkeypatch):
        """事件循环内可启动并优雅停止巡检。"""
        monkeypatch.setattr(settings, "TIMEOUT_CHECK_INTERVAL", 60)
        monkeypatch.setattr(
            task_recovery_service,
            "_scan_once",
            lambda: [],
        )
        task_recovery_service._monitor_task = None

        task_recovery_service.start_task_recovery()
        monitor = task_recovery_service._monitor_task
        assert monitor is not None
        await asyncio.sleep(0)
        assert not monitor.done()

        task_recovery_service.shutdown_task_recovery()
        assert task_recovery_service._monitor_task is None
        await asyncio.gather(monitor, return_exceptions=True)
        assert monitor.done()
