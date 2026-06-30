"""快速测试 API 端点集成测试（SubTask 9.7）。

覆盖范围：
- POST /api/v1/quick-test/launch：启动成功、未鉴权 401、非法 URL 422、
  ValueError 422、服务异常 503、HTTPException 透传、单用户限流 11 次→429；
- GET /api/v1/quick-test/{task_id}/status：查询成功、未鉴权 401、不存在 404、
  越权访问他人任务 404、空用例与已完成态字段映射；
- 辅助函数：_derive_stage 全状态/进度分支、_build_status_response 边界、
  _PerUserRateLimiter acquire/隔离/清理/reset。

测试策略：TestClient + 真实测试库（conftest 的 client/db/testUser/testProject/
authHeaders fixtures），mock QuickLauncher（monkeypatch 端点模块符号）避免真实
浏览器探索与 AI 调用。限流器每个用例前后 reset，避免跨用例计数污染。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import quick_test as quick_test_module
from app.api.v1.endpoints.quick_test import (
    _PerUserRateLimiter,
    _build_status_response,
    _derive_stage,
    launch_limiter,
)
from app.models.test_task import TaskStatus, TestTask
from app.models.user import User
from app.schemas.quick_test import QuickTestLaunchResponse
from app.utils.jwt_utils import get_password_hash

LAUNCH_URL = "/api/v1/quick-test/launch"
STATUS_URL = "/api/v1/quick-test/{task_id}/status"


@pytest.fixture(autouse=True)
def _resetLaunchLimiter():
    """每个用例前后清空限流计数，避免跨用例污染导致误触发 429。"""
    launch_limiter.reset()
    yield
    launch_limiter.reset()


def _patchLauncher(monkeypatch, launchFn):
    """替换端点模块内的 QuickLauncher 为可控假实现。

    launchFn: (url, description, credentials, user_id, session) -> QuickTestLaunchResponse
        或在其中抛出异常以模拟编排失败。
    """

    class _FakeLauncher:
        def __init__(self, *args, **kwargs):
            pass

        async def launch(self, url, description, credentials, user_id, session):
            return launchFn(url, description, credentials, user_id, session)

    monkeypatch.setattr(quick_test_module, "QuickLauncher", _FakeLauncher)


def _successResponse():
    return QuickTestLaunchResponse(
        task_id=1, project_id=2, estimated_duration_sec=60,
        websocket_channel="quick_test:1",
    )


def _makeTask(db, *, executor_id, project_id, status=TaskStatus.RUNNING,
              progress=50, case_ids=None, start_time=None):
    """在测试库创建 TestTask 并 flush 取 id。"""
    ids = [1, 2] if case_ids is None else case_ids
    task = TestTask(
        task_name="qt_task",
        project_id=project_id,
        case_ids=ids,
        executor_id=executor_id,
        status=status,
        total_count=len(ids),
        progress=progress,
        start_time=start_time,
    )
    db.add(task)
    db.flush()
    return task


class TestLaunch:
    def test_launch_success(self, client, authHeaders, monkeypatch):
        _patchLauncher(monkeypatch, lambda *a: _successResponse())
        resp = client.post(LAUNCH_URL, json={
            "url": "https://demo.playwright.dev/todomvc",
            "description": "重点测登录",
            "credentials": {"username": "u", "password": "p"},
        }, headers=authHeaders)
        assert resp.status_code == 200
        data = resp.json()
        assert data == {
            "task_id": 1, "project_id": 2,
            "estimated_duration_sec": 60, "websocket_channel": "quick_test:1",
        }

    def test_launch_unauthorized(self, client):
        resp = client.post(LAUNCH_URL, json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_launch_invalid_url_returns_400(self, client, authHeaders, monkeypatch):
        # spec 场景描述为 422，但项目全局 request_validation_exception_handler
        # 将 Pydantic schema 层校验错误统一转为 400（RESPONSE_CODE["VALIDATION_ERROR"]），
        # 此处遵循项目既有约定，422 偏差在完成报告中标注。
        _patchLauncher(monkeypatch, lambda *a: _successResponse())
        resp = client.post(LAUNCH_URL, json={"url": "not-a-url"}, headers=authHeaders)
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 400
        assert "errors" in body["data"]

    def test_launch_value_error_returns_422(self, client, authHeaders, monkeypatch):
        # 端点显式将 ValueError 转为 HTTPException(422)，http_exception_handler
        # 保留 status_code=422 并用统一响应体包装（msg 字段承载 detail）。
        def _raiseValueError(*a):
            raise ValueError("invalid url scheme")
        _patchLauncher(monkeypatch, _raiseValueError)
        resp = client.post(LAUNCH_URL, json={"url": "https://example.com"}, headers=authHeaders)
        assert resp.status_code == 422
        assert "invalid url scheme" in resp.json()["msg"]

    def test_launch_service_error_returns_503(self, client, authHeaders, monkeypatch):
        def _raiseRuntime(*a):
            raise RuntimeError("browser crashed")
        _patchLauncher(monkeypatch, _raiseRuntime)
        resp = client.post(LAUNCH_URL, json={"url": "https://example.com"}, headers=authHeaders)
        assert resp.status_code == 503

    def test_launch_http_exception_passthrough(self, client, authHeaders, monkeypatch):
        # 编排层抛 HTTPException 时应原样透传，不被通用 503 分支吞掉
        def _raiseHttp(*a):
            raise HTTPException(status_code=400, detail="bad request")
        _patchLauncher(monkeypatch, _raiseHttp)
        resp = client.post(LAUNCH_URL, json={"url": "https://example.com"}, headers=authHeaders)
        assert resp.status_code == 400

    def test_launch_rate_limit(self, client, authHeaders, monkeypatch):
        _patchLauncher(monkeypatch, lambda *a: _successResponse())
        codes = [
            client.post(LAUNCH_URL, json={"url": "https://example.com"}, headers=authHeaders).status_code
            for _ in range(11)
        ]
        assert codes[:10] == [200] * 10
        assert codes[10] == 429


class TestStatus:
    def test_status_success_running(self, client, authHeaders, db, testUser, testProject):
        task = _makeTask(db, executor_id=testUser.id, project_id=testProject.id,
                         status=TaskStatus.RUNNING, progress=50, case_ids=[1, 2, 3])
        resp = client.get(STATUS_URL.format(task_id=task.id), headers=authHeaders)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task.id
        assert data["status"] == "执行中"
        assert data["progress"] == 50
        assert data["current_stage"] == "case_generating"
        assert data["case_count"] == 3
        assert data["websocket_channel"] == f"quick_test:{task.id}"
        assert data["started_at"] is None

    def test_status_not_found(self, client, authHeaders):
        resp = client.get(STATUS_URL.format(task_id=999999), headers=authHeaders)
        assert resp.status_code == 404

    def test_status_unauthorized(self, client):
        resp = client.get(STATUS_URL.format(task_id=1))
        assert resp.status_code == 401

    def test_status_other_user_task_returns_404(self, client, authHeaders, db, testUser, testProject):
        other = User(
            username="qt_other", email="qt_other@test.com",
            password_hash=get_password_hash("x"), is_active=True,
        )
        db.add(other)
        db.flush()
        task = _makeTask(db, executor_id=other.id, project_id=testProject.id)
        resp = client.get(STATUS_URL.format(task_id=task.id), headers=authHeaders)
        assert resp.status_code == 404

    def test_status_pending_empty_cases(self, client, authHeaders, db, testUser, testProject):
        task = _makeTask(db, executor_id=testUser.id, project_id=testProject.id,
                        status=TaskStatus.PENDING, progress=0, case_ids=[])
        resp = client.get(STATUS_URL.format(task_id=task.id), headers=authHeaders)
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_count"] == 0
        assert data["current_stage"] == "pending"
        assert data["status"] == "等待执行"

    def test_status_completed_with_start_time(self, client, authHeaders, db, testUser, testProject):
        started = datetime(2026, 6, 27, 10, 30, 0)
        task = _makeTask(db, executor_id=testUser.id, project_id=testProject.id,
                        status=TaskStatus.COMPLETED, progress=100, case_ids=[1],
                        start_time=started)
        resp = client.get(STATUS_URL.format(task_id=task.id), headers=authHeaders)
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == "completed"
        assert data["status"] == "执行完成"
        assert data["started_at"].startswith("2026-06-27T10:30:00")


class TestDeriveStage:
    @pytest.mark.parametrize("status,progress,expected", [
        (TaskStatus.PENDING, 0, "pending"),
        (TaskStatus.RUNNING, 20, "site_exploring"),
        (TaskStatus.RUNNING, 45, "case_generating"),
        (TaskStatus.RUNNING, 75, "task_assembling"),
        (TaskStatus.RUNNING, 95, "executing"),
        (TaskStatus.COMPLETED, 100, "completed"),
        (TaskStatus.FAILED, 30, "failed"),
        (TaskStatus.STOPPED, 50, "stopped"),
    ])
    def test_derive_stage(self, status, progress, expected):
        task = SimpleNamespace(status=status, progress=progress)
        assert _derive_stage(task) == expected

    def test_derive_stage_none_progress(self):
        # progress 为 None 时应兜底为 0，落到 site_exploring
        task = SimpleNamespace(status=TaskStatus.RUNNING, progress=None)
        assert _derive_stage(task) == "site_exploring"


class TestBuildStatusResponse:
    def test_case_ids_none_returns_zero(self):
        task = SimpleNamespace(id=5, status=TaskStatus.PENDING, progress=0,
                               case_ids=None, start_time=None)
        resp = _build_status_response(task)
        assert resp.case_count == 0
        assert resp.started_at is None
        assert resp.websocket_channel == "quick_test:5"

    def test_unknown_status_label(self):
        task = SimpleNamespace(id=5, status=99, progress=0,
                               case_ids=[1], start_time=None)
        resp = _build_status_response(task)
        assert resp.status == "未知"


class TestPerUserRateLimiter:
    """内存模式限流测试（强制 _use_redis=False 隔离 Redis 环境）。

    Redis 模式测试见 TestPerUserRateLimiterRedis。
    """

    @staticmethod
    def _make_memory_limiter(max_requests: int, time_window: int) -> "_PerUserRateLimiter":
        """创建强制走内存模式的 limiter，避免测试环境 Redis 干扰。"""
        limiter = _PerUserRateLimiter(max_requests, time_window)
        limiter._use_redis = False
        limiter._redis_client = None
        return limiter

    def test_acquire_over_limit_raises_429(self):
        limiter = self._make_memory_limiter(max_requests=3, time_window=60)
        for _ in range(3):
            limiter.acquire(100)
        with pytest.raises(HTTPException) as exc:
            limiter.acquire(100)
        assert exc.value.status_code == 429

    def test_acquire_isolated_per_user(self):
        limiter = self._make_memory_limiter(max_requests=1, time_window=60)
        limiter.acquire(1)
        # 不同用户独立计数，不互相影响
        limiter.acquire(2)

    def test_cleanup_removes_expired(self):
        import time as _time
        limiter = self._make_memory_limiter(max_requests=2, time_window=1)
        limiter.acquire(200)
        # 将唯一记录改为过期，触发清理后应放行
        limiter._requests[200][0] = _time.time() - 5
        limiter.acquire(200)
        assert len(limiter._requests[200]) == 1

    def test_reset_clears_state(self):
        limiter = self._make_memory_limiter(max_requests=1, time_window=60)
        limiter.acquire(300)
        limiter.reset()
        assert limiter._requests == {}
        # reset 后可再次获取配额
        limiter.acquire(300)


class TestPerUserRateLimiterRedis:
    """Redis 模式限流测试（双模式扩展，Task #17）。

    验证 _PerUserRateLimiter 在 Redis 可用时正确使用 Sorted Set 滑动窗口，
    以及 Redis 运行时异常时降级到内存模式。
    """

    _TEST_USER_ID = 99990

    @pytest.fixture(autouse=True)
    def _cleanup_redis(self):
        """每个用例前后清理 Redis 中的测试 user 限流 key，避免跨用例计数污染。"""
        yield
        limiter = _PerUserRateLimiter(max_requests=100, time_window=60)
        if limiter._redis_client is not None:
            limiter._redis_client.delete(f"ratelimit:user:{self._TEST_USER_ID}")

    @staticmethod
    def _make_redis_limiter(max_requests: int, time_window: int) -> "_PerUserRateLimiter":
        """创建走 Redis 模式的 limiter，若 Redis 不可用则 skip。"""
        limiter = _PerUserRateLimiter(max_requests, time_window)
        if not limiter._use_redis:
            pytest.skip("Redis 不可用，跳过 Redis 模式测试")
        return limiter

    def test_redis_acquire_under_limit(self):
        """Redis 模式下未超限时应放行。"""
        limiter = self._make_redis_limiter(max_requests=5, time_window=60)
        if limiter._redis_client is not None:
            limiter._redis_client.delete(f"ratelimit:user:{self._TEST_USER_ID}")
        limiter.acquire(self._TEST_USER_ID)

    def test_redis_acquire_over_limit_raises_429(self):
        """Redis 模式下超限应抛 429。"""
        limiter = self._make_redis_limiter(max_requests=2, time_window=60)
        if limiter._redis_client is not None:
            limiter._redis_client.delete(f"ratelimit:user:{self._TEST_USER_ID}")
        limiter.acquire(self._TEST_USER_ID)
        limiter.acquire(self._TEST_USER_ID)
        with pytest.raises(HTTPException) as exc:
            limiter.acquire(self._TEST_USER_ID)
        assert exc.value.status_code == 429

    def test_redis_isolated_per_user(self):
        """Redis 模式下不同 user_id 独立计数。"""
        limiter = self._make_redis_limiter(max_requests=1, time_window=60)
        other_user = 99991
        if limiter._redis_client is not None:
            limiter._redis_client.delete(f"ratelimit:user:{self._TEST_USER_ID}")
            limiter._redis_client.delete(f"ratelimit:user:{other_user}")
        try:
            limiter.acquire(self._TEST_USER_ID)
            limiter.acquire(other_user)
        finally:
            if limiter._redis_client is not None:
                limiter._redis_client.delete(f"ratelimit:user:{other_user}")

    def test_redis_runtime_exception_falls_back_to_memory(self):
        """Redis 运行时异常应降级到内存模式，不阻断请求。"""
        limiter = self._make_redis_limiter(max_requests=5, time_window=60)
        if limiter._redis_client is not None:
            limiter._redis_client.delete(f"ratelimit:user:{self._TEST_USER_ID}")

        original_pipe = limiter._redis_client.pipeline
        call_count = {"n": 0}

        def _flaky_pipe():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("redis connection lost")
            return original_pipe()

        limiter._redis_client.pipeline = _flaky_pipe
        limiter.acquire(self._TEST_USER_ID)
        assert call_count["n"] == 1
        assert len(limiter._requests[self._TEST_USER_ID]) == 1
