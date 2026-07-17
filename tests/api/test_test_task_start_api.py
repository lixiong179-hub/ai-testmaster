"""TaskStartConfig.execution_mode 白名单逻辑测试。

覆盖范围:
    1. start_test_task 端点的 execution_mode 白名单分支（默认值/合法值/非法值回退）
    2. mobile_device_id 透传
    3. 错误路径（任务不存在/状态不允许/executor 异常标记失败）

设计说明:
    - 通过 monkeypatch 替换 TestExecutionEngineV2 为记录调用的 mock executor，
      避免触发真实测试用例执行（spec: 真实环境测试，但执行引擎属于下游副作用，
      本测试聚焦白名单逻辑，executor 行为由 executor 自身的测试覆盖）。
    - TestTask 直接通过 async_db fixture 创建，避免 API 创建链路的额外依赖。
    - 使用 tests/api/conftest.py 的 async fixture（async_auth_client / async_db /
      async_test_project / async_test_user），端测双迁。
    - 端点 start_test_task 已迁移为直接 async 调用，使用请求级 db 会话独立 commit；
      测试断言 task.status/end_time 时需重新查询（async_db 中的实例已过期），
      禁止使用 async_db.refresh(task)，否则会抛 InvalidRequestError。
"""
import pytest
from sqlalchemy import select
from app.models.test_task import TestTask


async def _make_task(async_db, project, user, status: int = 0) -> TestTask:
    """创建一个 TestTask 记录（status 默认 0=PENDING）。"""
    task = TestTask(
        task_name="execution_mode_test_task",
        project_id=project.id,
        case_ids=[],
        executor_id=user.id,
        status=status,
    )
    async_db.add(task)
    await async_db.flush()
    return task


@pytest.fixture
def mock_executor(monkeypatch):
    """替换 TestExecutionEngineV2 为记录调用的 mock。

    返回 mock_executor 对象，可通过 mock_executor.calls 查看调用参数列表，
    通过 mock_executor.raise_exc 设置下次调用抛出的异常。
    """

    class _Call:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _MockExecutor:
        def __init__(self, db):
            self.db = db

        async def execute_test_task(self, **kwargs):
            mock_executor.calls.append(_Call(**kwargs))
            if mock_executor.raise_exc is not None:
                exc = mock_executor.raise_exc
                mock_executor.raise_exc = None
                raise exc
            return {"task_id": kwargs.get("task_id"), "results": []}

    mock_executor.calls = []
    mock_executor.raise_exc = None
    monkeypatch.setattr(
        "app.api.v1.endpoints.test_task.TestExecutionEngineV2", _MockExecutor
    )
    return mock_executor


class TestExecutionModeWhitelist:
    """execution_mode 白名单逻辑测试（test_task.py L287-296）。"""

    async def test_default_mode_when_config_none(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """不传 body（config=None）时 execution_mode 应回退到默认 'smart'。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(f"/api/v1/test-task/{task.id}/start")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["execution_mode"] == "smart"
        assert mock_executor.calls[0].kwargs["execution_mode"] == "smart"

    async def test_default_mode_when_config_empty(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """传空 body（config={}）时 execution_mode 应回退到 'smart'。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"

    @pytest.mark.parametrize("mode", [
        "preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"
    ])
    async def test_valid_mode_accepted(self, mode, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """合法 execution_mode 应被原样接受并透传给 executor。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": mode},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == mode
        assert mock_executor.calls[0].kwargs["execution_mode"] == mode

    async def test_invalid_mode_falls_back_to_smart(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """非法 execution_mode 应回退到 'smart' 而非报错。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "invalid_mode_name"},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"
        assert mock_executor.calls[0].kwargs["execution_mode"] == "smart"

    async def test_empty_string_mode_falls_back_to_smart(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """空字符串 execution_mode 应回退到 'smart'（L290: config.execution_mode or 'smart'）。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": ""},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"

    async def test_null_mode_falls_back_to_smart(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """null execution_mode 应回退到 'smart'（L290: config.execution_mode or 'smart'）。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": None},
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"


class TestMobileDeviceIdPassThrough:
    """mobile_device_id 透传测试（L291）。"""

    async def test_mobile_device_id_passed_to_executor(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """mobile_device_id 应透传给 executor。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "mobile_realtime", "mobile_device_id": "device-001"},
        )

        assert resp.status_code == 200
        assert mock_executor.calls[0].kwargs["mobile_device_id"] == "device-001"

    async def test_mobile_device_id_none_when_not_provided(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """未提供 mobile_device_id 时应传 None。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "smart"},
        )

        assert mock_executor.calls[0].kwargs["mobile_device_id"] is None


class TestStartTaskErrorPaths:
    """start_test_task 错误路径测试。"""

    async def test_task_not_found_returns_404(self, async_auth_client, mock_executor):
        """不存在的 task_id 应返回 404。"""
        resp = await async_auth_client.post(
            "/api/v1/test-task/999999/start",
            json={"execution_mode": "smart"},
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("status, label", [
        (1, "RUNNING"), (2, "COMPLETED"), (4, "STOPPED"),
    ])
    async def test_disallowed_status_returns_400(self, status, label, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """任务状态不在 [0, 3] 时应返回 400（L281-285）。"""
        task = await _make_task(async_db, async_test_project, async_test_user, status=status)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "smart"},
        )
        assert resp.status_code == 400
        assert "状态不允许" in resp.json()["msg"]
        assert mock_executor.calls == []

    async def test_failed_status_allows_restart(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """status=3（FAILED）允许重新启动（L281: status in [0, 3]）。"""
        task = await _make_task(async_db, async_test_project, async_test_user, status=3)
        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "smart"},
        )
        assert resp.status_code == 200
        assert len(mock_executor.calls) == 1

    async def test_executor_exception_marks_task_failed(self, async_auth_client, async_test_project, async_test_user, async_db, mock_executor):
        """executor 抛异常时应将 task.status 标记为 2（FAILED）（L310-314）。"""
        task = await _make_task(async_db, async_test_project, async_test_user)
        mock_executor.raise_exc = RuntimeError("executor boom")

        resp = await async_auth_client.post(
            f"/api/v1/test-task/{task.id}/start",
            json={"execution_mode": "smart"},
        )

        assert resp.status_code == 200
        # 端点用请求级 db 会话独立 commit，async_db 中的 task 实例已过期，
        # 必须重新查询以拿到最新 status/end_time。
        result = await async_db.execute(
            select(TestTask).where(TestTask.id == task.id)
        )
        task = result.scalars().first()
        assert task.status == 2
        assert task.end_time is not None

    async def test_unauthorized_returns_401(self, async_client, mock_executor):
        """无 Authorization header 应返回 401。"""
        resp = await async_client.post(
            "/api/v1/test-task/1/start",
            json={"execution_mode": "smart"},
        )
        assert resp.status_code in (401, 403)
