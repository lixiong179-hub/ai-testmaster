"""TaskStartConfig.execution_mode 白名单逻辑测试。

覆盖范围:
    1. start_test_task 端点的 execution_mode 白名单分支（默认值/合法值/非法值回退）
    2. mobile_device_id 透传
    3. 错误路径（任务不存在/状态不允许/executor 异常标记失败）

设计说明:
    - 通过 monkeypatch 替换 TestExecutionEngineV2 为记录调用的 mock executor，
      避免触发真实测试用例执行（spec: 真实环境测试，但执行引擎属于下游副作用，
      本测试聚焦白名单逻辑，executor 行为由 executor 自身的测试覆盖）。
    - TestTask 直接通过 db fixture 创建，避免 API 创建链路的额外依赖。
"""
import pytest
from app.models.test_task import TestTask


def _make_task(db, project, user, status: int = 0) -> TestTask:
    """创建一个 TestTask 记录（status 默认 0=PENDING）。"""
    task = TestTask(
        task_name="execution_mode_test_task",
        project_id=project.id,
        case_ids=[],
        executor_id=user.id,
        status=status,
    )
    db.add(task)
    db.flush()
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

    def test_default_mode_when_config_none(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """不传 body（config=None）时 execution_mode 应回退到默认 'smart'。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(f"/api/v1/test_task/{task.id}/start", headers=authHeaders)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["execution_mode"] == "smart"
        assert mock_executor.calls[0].kwargs["execution_mode"] == "smart"

    def test_default_mode_when_config_empty(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """传空 body（config={}）时 execution_mode 应回退到 'smart'。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"

    @pytest.mark.parametrize("mode", [
        "preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"
    ])
    def test_valid_mode_accepted(self, mode, client, authHeaders, testProject, testUser, db, mock_executor):
        """合法 execution_mode 应被原样接受并透传给 executor。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": mode},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == mode
        assert mock_executor.calls[0].kwargs["execution_mode"] == mode

    def test_invalid_mode_falls_back_to_smart(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """非法 execution_mode 应回退到 'smart' 而非报错。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "invalid_mode_name"},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"
        assert mock_executor.calls[0].kwargs["execution_mode"] == "smart"

    def test_empty_string_mode_falls_back_to_smart(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """空字符串 execution_mode 应回退到 'smart'（L290: config.execution_mode or 'smart'）。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": ""},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"

    def test_null_mode_falls_back_to_smart(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """null execution_mode 应回退到 'smart'（L290: config.execution_mode or 'smart'）。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": None},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["execution_mode"] == "smart"


class TestMobileDeviceIdPassThrough:
    """mobile_device_id 透传测试（L291）。"""

    def test_mobile_device_id_passed_to_executor(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """mobile_device_id 应透传给 executor。"""
        task = _make_task(db, testProject, testUser)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "mobile_realtime", "mobile_device_id": "device-001"},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        assert mock_executor.calls[0].kwargs["mobile_device_id"] == "device-001"

    def test_mobile_device_id_none_when_not_provided(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """未提供 mobile_device_id 时应传 None。"""
        task = _make_task(db, testProject, testUser)
        client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "smart"},
            headers=authHeaders,
        )

        assert mock_executor.calls[0].kwargs["mobile_device_id"] is None


class TestStartTaskErrorPaths:
    """start_test_task 错误路径测试。"""

    def test_task_not_found_returns_404(self, client, authHeaders, mock_executor):
        """不存在的 task_id 应返回 404。"""
        resp = client.post(
            "/api/v1/test_task/999999/start",
            json={"execution_mode": "smart"},
            headers=authHeaders,
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("status, label", [
        (1, "RUNNING"), (2, "COMPLETED"), (4, "STOPPED"),
    ])
    def test_disallowed_status_returns_400(self, status, label, client, authHeaders, testProject, testUser, db, mock_executor):
        """任务状态不在 [0, 3] 时应返回 400（L281-285）。"""
        task = _make_task(db, testProject, testUser, status=status)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "smart"},
            headers=authHeaders,
        )
        assert resp.status_code == 400
        assert "状态不允许" in resp.json()["msg"]
        assert mock_executor.calls == []

    def test_failed_status_allows_restart(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """status=3（FAILED）允许重新启动（L281: status in [0, 3]）。"""
        task = _make_task(db, testProject, testUser, status=3)
        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "smart"},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        assert len(mock_executor.calls) == 1

    def test_executor_exception_marks_task_failed(self, client, authHeaders, testProject, testUser, db, mock_executor):
        """executor 抛异常时应将 task.status 标记为 2（FAILED）（L310-314）。"""
        task = _make_task(db, testProject, testUser)
        mock_executor.raise_exc = RuntimeError("executor boom")

        resp = client.post(
            f"/api/v1/test_task/{task.id}/start",
            json={"execution_mode": "smart"},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        db.refresh(task)
        assert task.status == 2
        assert task.end_time is not None

    def test_unauthorized_returns_401(self, client, mock_executor):
        """无 Authorization header 应返回 401。"""
        resp = client.post(
            "/api/v1/test_task/1/start",
            json={"execution_mode": "smart"},
        )
        assert resp.status_code in (401, 403)
