import uuid
import asyncio
import pytest
from app.services.task_service import TaskService
from app.models.test_task import TestTask, TaskStatus
from app.models.project import Project
from tests.helpers import createTestUser, createTestProject


class TestTaskServiceStartTask:
    """验证 TaskService.start_task 新签名 (task_id, project_id, case_ids) 的行为。

    新签名不返回字典，仅注册任务到 running_tasks 并通过 asyncio.create_task
    负载调度 _execute_task。这里通过 monkeypatch 将 create_task 替换为空操作，
    避免触发真实执行链路（_execute_task 会启动浏览器、写入数据库）。
    """

    def test_start_task_registers_running_state(self, monkeypatch):
        """start_task 应将任务注册到 running_tasks 并标记为 running。"""
        service = TaskService()
        invoked = {}

        def fake_create_task(coro):
            invoked["called"] = True
            coro.close()  # 关闭未消费的协程避免 RuntimeWarning

            class _Dummy:
                def cancel(self):
                    pass

            return _Dummy()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        service.start_task(task_id=1001, project_id=10, case_ids=[1, 2, 3])

        assert invoked.get("called") is True
        assert 1001 in service.running_tasks
        entry = service.running_tasks[1001]
        assert entry["status"] == "running"
        assert entry["project_id"] == 10
        assert entry["case_ids"] == [1, 2, 3]
        assert entry["current_case"] == 0

    def test_start_task_does_not_raise_on_duplicate(self, monkeypatch):
        """对同一 task_id 重复调用 start_task 不抛异常（覆盖 running 状态）。"""
        service = TaskService()

        def fake_create_task(coro):
            coro.close()

            class _Dummy:
                def cancel(self):
                    pass

            return _Dummy()

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        service.start_task(task_id=2002, project_id=20, case_ids=[1])
        # 再次启动同一任务不应抛出异常
        service.start_task(task_id=2002, project_id=20, case_ids=[1, 2])
        assert service.running_tasks[2002]["case_ids"] == [1, 2]


class TestTaskServiceStopTask:
    """验证 TaskService.stop_task 新签名 (task_id) 的行为。

    新签名仅修改 running_tasks[task_id]["status"] = "stopped"，
    不再返回字典、不再访问数据库、不再校验任务存在性。
    """

    def test_stop_task_marks_stopped(self):
        """stop_task 应将 running_tasks 中对应任务状态置为 stopped。"""
        service = TaskService()
        service.running_tasks[3003] = {
            "status": "running",
            "project_id": 30,
            "case_ids": [1],
            "current_case": 0,
            "success_count": 0,
            "fail_count": 0,
        }

        service.stop_task(task_id=3003)

        assert service.running_tasks[3003]["status"] == "stopped"

    def test_stop_task_unknown_id_is_noop(self):
        """对未在 running_tasks 中的 task_id 调用 stop_task 应静默无异常。"""
        service = TaskService()
        # 不应抛出 KeyError 或其他异常
        service.stop_task(task_id=99999)
        assert 99999 not in service.running_tasks


class TestTaskServiceInit:
    """验证 TaskService() 无参数构造函数的初始化行为。"""

    def test_init_no_args_sets_defaults(self):
        """TaskService() 应初始化 running_tasks 为空字典。"""
        service = TaskService()
        assert service.running_tasks == {}

    def test_get_push_service_lazy_initial_none(self):
        """TaskPushMixin.__init__ 应将 _push_service 初始化为 None（延迟加载）。"""
        service = TaskService()
        assert service._push_service is None


class TestTaskModel:
    def test_create_task_model(self, db, testUser, testProject):
        task = TestTask(
            task_name=f"model_task_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1, 2, 3],
            executor_id=testUser.id,
            status=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.id is not None
        assert task.status == 0
        assert task.case_ids == [1, 2, 3]
        assert task.total_count == 0
        assert task.success_count == 0
        assert task.fail_count == 0

    def test_task_status_labels(self):
        assert TaskStatus.PENDING == 0
        assert TaskStatus.RUNNING == 1
        assert TaskStatus.COMPLETED == 2
        assert TaskStatus.FAILED == 3
        assert TaskStatus.STOPPED == 4
        assert 0 in TaskStatus.LABELS
        assert TaskStatus.LABELS[0] == "等待执行"

    def test_task_default_values(self, db, testUser, testProject):
        task = TestTask(
            task_name=f"default_task_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[],
            executor_id=testUser.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.progress == 0
        assert task.success_count == 0
        assert task.fail_count == 0
        assert task.total_count == 0

    def test_task_with_project_relationship(self, db, testUser, testProject):
        task = TestTask(
            task_name=f"rel_task_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[],
            executor_id=testUser.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.project_id == testProject.id
