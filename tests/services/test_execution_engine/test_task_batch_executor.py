"""TaskBatchExecutorMixin.execute_test_task 编排护栏（G-8 B4 拆分前置测试）。

用最小桩替换 DB / 前置服务 / 用例执行，锁定任务状态流转、计数、异常映射与清理时机。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ExecStatus
from app.models.test_task import TaskStatus
from app.services.test_execution_engine.models import ExecutionError, ExecutionStatus
from app.services.test_execution_engine.task_batch_executor_mixin import TaskBatchExecutorMixin


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _query(first=None, all_items=None) -> MagicMock:
    query = MagicMock()
    query.filter.return_value.first.return_value = first
    query.filter.return_value.all.return_value = all_items if all_items is not None else []
    return query


def _mock_precondition() -> MagicMock:
    """已就绪的前置服务桩（不触发初始化/清理分支）。"""
    precondition = MagicMock()
    precondition.initialize = AsyncMock()
    precondition.cleanup = AsyncMock()
    precondition.read_test_object_info = AsyncMock()
    precondition.execute_web_precondition = AsyncMock(return_value=None)
    return precondition


class _Stub(TaskBatchExecutorMixin):
    """只实现编排所需协作者的最小桩。"""

    def __init__(
        self,
        db: MagicMock,
        *,
        precondition_service=None,
        allow_own_precondition: bool = False,
        cases=None,
        case_result=None,
        case_error: Exception | None = None,
        blocked: bool = False,
        nav_ok: bool = True,
        nav_level: str | None = "L1",
    ) -> None:
        self.db = db
        if precondition_service is None and not allow_own_precondition:
            precondition_service = _mock_precondition()
        self.precondition_service = precondition_service
        self.browser = None
        self.locator_service = object()
        self._visibility_config = None
        self._case_results = {}
        self._step_results = []
        self._pending_cases = []
        self._anchor_step_index = {}
        self._cases = cases or []
        self._case_result = case_result
        self._case_error = case_error
        self._blocked = blocked
        self._nav_ok = nav_ok
        self._nav_level = nav_level
        self.marked_blocked = False
        self.saved_snapshots = False

    def _init_dependency_state(self) -> None:
        return None

    def _resolve_execution_order(self, cases):
        return self._cases

    def _init_api_setup_state(self) -> None:
        return None

    def _build_anchor_step_index(self, cases):
        return {}

    def _should_skip_as_blocked(self, case) -> bool:
        return self._blocked

    def _mark_dependents_blocked(self, case, sorted_cases, case_results) -> None:
        self.marked_blocked = True

    async def _navigate_to_dependency_anchor(self, case):
        return self._nav_ok, self._nav_level

    async def _save_main_flow_snapshots(self, case, step_results) -> None:
        self.saved_snapshots = True

    async def execute_test_case(self, **kwargs):
        if self._case_error:
            raise self._case_error
        return self._case_result

    def _get_task_summary(self, task_id):
        return {"task_id": task_id}


@pytest.fixture
def visibility_ok():
    with (
        patch("app.services.visibility_config.VisibilityConfigService") as vis,
        patch("app.services.visibility_config.merger.VisibilityConfigMerger") as merger,
    ):
        vis.return_value.get_project_config.return_value = {}
        vis.return_value.get_task_config.return_value = {}
        merger.merge.return_value = {}
        yield vis, merger


def _task(task_id: int = 1, project_id: int = 10) -> _Obj:
    return _Obj(id=task_id, project_id=project_id, status=None, start_time=None, error_message=None, end_time=None)


def _project(project_id: int = 10, web_env_configs=None) -> _Obj:
    return _Obj(id=project_id, web_env_configs=web_env_configs)


def _result(case_id: int = 1) -> _Obj:
    return _Obj(case_id=case_id, exec_status=None, exec_time=None, exec_log="", error_msg=None, defect_evidence=None)


def _case(case_id: int = 1, depends_on=None) -> _Obj:
    return _Obj(id=case_id, case_no=f"TC-{case_id}", depends_on=depends_on)


def _case_result(status=ExecutionStatus.PASSED, **kwargs) -> _Obj:
    base = {"status": status, "failure_category": None, "error_message": "", "steps": []}
    base.update(kwargs)
    return _Obj(**base)


async def test_task_not_found_raises(visibility_ok):
    db = MagicMock()
    db.query.side_effect = [_query(first=None)]
    engine = _Stub(db)

    with pytest.raises(ExecutionError, match="测试任务不存在"):
        await engine.execute_test_task(1)


async def test_project_not_found_raises(visibility_ok):
    db = MagicMock()
    db.query.side_effect = [_query(first=_task()), _query(first=None)]
    engine = _Stub(db)

    with pytest.raises(ExecutionError, match="项目不存在"):
        await engine.execute_test_task(1)


async def test_empty_results_completes_task(visibility_ok):
    db = MagicMock()
    task = _task()
    db.query.side_effect = [_query(first=task), _query(first=_project()), _query(all_items=[])]
    engine = _Stub(db)

    summary = await engine.execute_test_task(1)

    assert summary == {"task_id": 1}
    assert task.status == TaskStatus.COMPLETED
    assert task.end_time is not None


async def test_all_cases_passed_marks_completed(visibility_ok):
    db = MagicMock()
    task = _task()
    test_result = _result()
    case = _case()
    db.query.side_effect = [
        _query(first=task),
        _query(first=_project()),
        _query(all_items=[test_result]),
        _query(all_items=[case]),
    ]
    engine = _Stub(db, cases=[case], case_result=_case_result())

    await engine.execute_test_task(1)

    assert task.status == TaskStatus.COMPLETED
    assert task.error_message is None
    assert test_result.exec_status == ExecStatus.PASSED
    assert engine.saved_snapshots is True


async def test_blocked_case_marks_task_failed(visibility_ok):
    db = MagicMock()
    task = _task()
    test_result = _result()
    case = _case()
    db.query.side_effect = [
        _query(first=task),
        _query(first=_project()),
        _query(all_items=[test_result]),
        _query(all_items=[case]),
    ]
    engine = _Stub(db, cases=[case], blocked=True)

    await engine.execute_test_task(1)

    assert test_result.exec_status == ExecStatus.BLOCKED
    assert "上游阻塞" in test_result.exec_log
    assert task.status == TaskStatus.FAILED
    assert "1 个用例阻塞" in task.error_message


async def test_navigation_failure_sets_category_and_log(visibility_ok):
    db = MagicMock()
    task = _task()
    test_result = _result()
    case = _case(depends_on="主干用例")
    db.query.side_effect = [
        _query(first=task),
        _query(first=_project()),
        _query(all_items=[test_result]),
        _query(all_items=[case]),
    ]
    failed_result = _case_result(status=ExecutionStatus.FAILED, error_message="boom")
    engine = _Stub(db, cases=[case], case_result=failed_result, nav_ok=False)

    await engine.execute_test_task(1)

    assert failed_result.failure_category is not None
    assert failed_result.failure_category.name == "NAVIGATION_FAILURE"
    assert test_result.exec_status == ExecStatus.FAILED
    assert test_result.exec_log.startswith("[导航失败]")
    assert task.status == TaskStatus.FAILED
    assert engine.marked_blocked is True


async def test_case_exception_marks_failed_and_blocks_dependents(visibility_ok):
    db = MagicMock()
    task = _task()
    test_result = _result()
    case = _case()
    db.query.side_effect = [
        _query(first=task),
        _query(first=_project()),
        _query(all_items=[test_result]),
        _query(all_items=[case]),
    ]
    engine = _Stub(db, cases=[case], case_error=RuntimeError("step exploded"))

    await engine.execute_test_task(1)

    assert test_result.exec_status == ExecStatus.FAILED
    assert test_result.error_msg == "step exploded"
    assert task.status == TaskStatus.FAILED
    assert "1 个用例失败" in task.error_message
    assert engine.marked_blocked is True


async def test_outer_exception_marks_task_failed_and_wraps(visibility_ok):
    db = MagicMock()
    task = _task()
    failing_query = MagicMock()
    failing_query.filter.side_effect = RuntimeError("db down")
    db.query.side_effect = [_query(first=task), _query(first=_project()), failing_query]
    engine = _Stub(db)

    with pytest.raises(ExecutionError, match="任务执行失败"):
        await engine.execute_test_task(1)

    assert task.status == TaskStatus.FAILED
    assert "任务执行异常中断" in task.error_message


async def test_visibility_config_failure_is_non_blocking(visibility_ok):
    vis, _ = visibility_ok
    vis.side_effect = RuntimeError("config broken")
    db = MagicMock()
    task = _task()
    db.query.side_effect = [_query(first=task), _query(first=_project()), _query(all_items=[])]
    engine = _Stub(db)

    await engine.execute_test_task(1)

    assert engine._visibility_config is None
    assert task.status == TaskStatus.COMPLETED


async def test_owns_precondition_service_is_initialized_and_cleaned(visibility_ok):
    precondition = MagicMock()
    precondition.initialize = AsyncMock()
    precondition.cleanup = AsyncMock()
    precondition.read_test_object_info = AsyncMock()
    precondition.execute_web_precondition = AsyncMock(return_value=None)

    db = MagicMock()
    task = _task()
    db.query.side_effect = [_query(first=task), _query(first=_project()), _query(all_items=[])]
    engine = _Stub(db, precondition_service=None, allow_own_precondition=True)

    with patch("app.services.precondition_service.PreconditionService", return_value=precondition):
        await engine.execute_test_task(1)

    precondition.initialize.assert_awaited_once()
    precondition.read_test_object_info.assert_awaited_once()
    precondition.cleanup.assert_awaited_once()
