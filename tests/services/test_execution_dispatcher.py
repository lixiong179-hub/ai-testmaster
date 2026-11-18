"""R5-1 阶段二：执行任务投递层（入队 + 原子领取）测试。

覆盖：
    - 入队：置 PENDING、重置进度与耗时、允许暂停任务重新入队
    - 领取：PENDING → RUNNING，返回任务 ID
    - 防重复：同一任务不能被领取两次（条件更新 rowcount 判定）
    - 拒绝重复入队：RUNNING 任务入队抛 ValueError
    - 兜底：执行异常时任务被标记 FAILED

说明：真实多副本并发领取（3 executor 同时抢同一任务）由
`docker compose up -d --scale executor=3` 的部署级验收覆盖；
本文件用「第二次领取返回 None」锁定条件更新的互斥语义。
"""

import uuid

import pytest

from app.models.project import Project
from app.models.test_task import TaskStatus, TestTask
from app.services.execution_dispatcher import ExecutionDispatcher


@pytest.fixture
def seed_task(db, testUser):
    """创建项目 + 排队中的测试任务。"""
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"dispatcher_{suffix}",
        user_id=testUser.id,
        description="投递层测试项目",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    task = TestTask(
        task_name=f"投递任务_{suffix}",
        project_id=project.id,
        case_ids=[1, 2],
        executor_id=testUser.id,
        status=TaskStatus.PENDING,
        total_count=2,
        progress=0,
    )
    db.add(task)
    db.flush()
    return {"project": project, "task": task}


def _reload(db, task_id: int) -> TestTask:
    db.expire_all()
    return db.query(TestTask).filter(TestTask.id == task_id).first()


class TestEnqueue:
    def test_enqueue_sets_pending_and_resets_progress(self, db, seed_task):
        """入队把任务置为 PENDING，并清空进度/耗时/计数。"""
        task = seed_task["task"]
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.success_count = 2
        task.fail_count = 0
        db.flush()

        info = ExecutionDispatcher(db).enqueue(task.id)

        assert info["task_id"] == task.id
        assert info["status"] == TaskStatus.PENDING
        assert info["status_label"] == "排队中"
        refreshed = _reload(db, task.id)
        assert refreshed.status == TaskStatus.PENDING
        assert refreshed.progress == 0
        assert refreshed.success_count == 0
        assert refreshed.start_time is None

    def test_enqueue_rejects_running_task(self, db, seed_task):
        """正在执行的任务不允许重复入队（409 语义）。"""
        task = seed_task["task"]
        task.status = TaskStatus.RUNNING
        db.flush()

        with pytest.raises(ValueError, match="正在执行"):
            ExecutionDispatcher(db).enqueue(task.id)

    def test_enqueue_unknown_task_raises(self, db):
        with pytest.raises(ValueError, match="不存在"):
            ExecutionDispatcher(db).enqueue(99999999)


class TestClaim:
    def test_claim_marks_running_and_returns_id(self, db, seed_task):
        """领取成功：PENDING → RUNNING，写入 start_time。"""
        task_id = ExecutionDispatcher(db).claim_next(task_id=seed_task["task"].id)

        assert task_id == seed_task["task"].id
        refreshed = _reload(db, seed_task["task"].id)
        assert refreshed.status == TaskStatus.RUNNING
        assert refreshed.start_time is not None

    def test_second_claim_returns_none(self, db, seed_task):
        """同一任务只能被领取一次（防多副本重复执行）。"""
        dispatcher = ExecutionDispatcher(db)
        first = dispatcher.claim_next(task_id=seed_task["task"].id)
        second = dispatcher.claim_next(task_id=seed_task["task"].id)

        assert first == seed_task["task"].id
        assert second is None

    def test_claim_ignores_non_pending_tasks(self, db, seed_task):
        """RUNNING/COMPLETED 任务不进入候选集。"""
        task = seed_task["task"]
        task.status = TaskStatus.COMPLETED
        db.flush()

        assert ExecutionDispatcher(db).claim_next(task_id=task.id) is None

    def test_mark_failed_sets_status_and_end_time(self, db, seed_task):
        """executor 执行异常兜底：标记 FAILED 并写 end_time。"""
        dispatcher = ExecutionDispatcher(db)
        task_id = dispatcher.claim_next(task_id=seed_task["task"].id)
        dispatcher.mark_failed(task_id, "browser crashed")

        refreshed = _reload(db, task_id)
        assert refreshed.status == TaskStatus.FAILED
        assert refreshed.end_time is not None
