"""R1-2: `/api/v1/agents/sessions/run` 端点（run_session）单元测试。

设计说明 —— 为什么不走 HTTP 客户端：
    本仓库 `tests/api/conftest.py` 的 `async_db` fixture 与 `async_auth_client`
    （HTTP 客户端）不在同一事件循环，且首次 run 请求会触发 app 侧初始化，
    混合使用会抛 "Task ... got Future attached to a different loop"。
    故本文件改为**直接 await 端点函数**的单元风格：mock db 与权限校验，
    只验证端点契约（驱动 Runtime → 提交事务 → 包装响应 → 异常映射）。
    真实落库行为由 `SessionService` / `AgentRuntime` 自身的测试覆盖。

覆盖：
    - 成功：Runtime 被调用且参数正确；返回终态 status 与 token_cost；db.commit 被调用
    - artifact：合法 → 转为 Artifact 实例传入；未注册类型 / 缺 artifact_type → 400
    - 异常：Runtime 抛异常 → 500；未注册 agent_type → 400
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.agents import run_session
from app.models.agent_session import AgentSession
from app.schemas.agent import SessionCreateRequest
from app.services.agent.exceptions import AgentError

_TARGET = "app.api.v1.endpoints.agents._build_runtime"
_PERM = "app.api.v1.endpoints.agents.verify_project_permission_async"


def _make_db() -> MagicMock:
    """构造 AsyncSession 替身：commit 为异步可等待。"""
    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_session(status="completed", token_cost=10) -> AgentSession:
    """构造不落库的 AgentSession 实例（仅供响应序列化）。"""
    return AgentSession(
        id=1,
        project_id=100,
        agent_type="test_generation",
        status=status,
        token_cost=token_cost,
        iteration_count=1,
        loop_detected=False,
        created_by=7,
    )


class FakeRuntime:
    """AgentRuntime 替身：记录调用参数并返回终态会话。"""

    def __init__(self, db, calls_sink=None, final_status="completed", raise_exc=None):
        self.db = db
        self.calls = calls_sink if calls_sink is not None else []
        self.final_status = final_status
        self.raise_exc = raise_exc

    async def run(
        self,
        agent_type,
        project_id,
        initial_artifacts,
        execution_callback=None,
        created_by=None,
    ):
        self.calls.append(
            {
                "agent_type": agent_type,
                "project_id": project_id,
                "initial_artifacts": initial_artifacts,
                "created_by": created_by,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return _make_session(status=self.final_status)


def _runtime_factory(calls_sink, **kwargs):
    def _build(db):
        return FakeRuntime(db, calls_sink=calls_sink, **kwargs)
    return _build


@pytest.fixture
def _no_perm_check():
    """跳过项目归属校验（该逻辑由既有测试覆盖）。"""
    with patch(_PERM, new=AsyncMock()) as mock_perm:
        yield mock_perm


class TestRunSessionSuccess:
    async def test_run_drives_runtime_and_commits(self, _no_perm_check):
        """端点驱动 Runtime，返回终态会话并提交事务。"""
        db = _make_db()
        calls = []
        req = SessionCreateRequest(agent_type="test_generation", project_id=100)
        user = MagicMock(id=7)

        with patch(_TARGET, side_effect=_runtime_factory(calls)):
            result = await run_session(req=req, db=db, current_user=user)

        # 1) Runtime 被调用且参数正确
        assert len(calls) == 1
        assert calls[0]["agent_type"] == "test_generation"
        assert calls[0]["project_id"] == 100
        assert calls[0]["created_by"] == 7

        # 2) 响应为终态，token_cost > 0（证明 Runtime 真跑，非仅回显）
        assert result["code"] == 200
        data = result["data"]
        assert data["status"] in ("completed", "failed")
        assert data["status"] == "completed"
        assert data["token_cost"] > 0

        # 3) 事务由端点提交（Runtime 自身只 flush 不 commit）
        db.commit.assert_awaited_once()

        # 4) 归属校验被执行
        _no_perm_check.assert_awaited_once()

    async def test_run_failed_status_is_returned(self, _no_perm_check):
        """Runtime 以 failed 结束时，端点如实返回 failed。"""
        db = _make_db()
        calls = []
        req = SessionCreateRequest(agent_type="locator_healing", project_id=100)

        with patch(
            _TARGET, side_effect=_runtime_factory(calls, final_status="failed")
        ):
            result = await run_session(
                req=req, db=db, current_user=MagicMock(id=7)
            )

        assert result["code"] == 200
        assert result["data"]["status"] == "failed"

    async def test_run_passes_valid_artifact(self, _no_perm_check):
        """合法 artifact 被校验为 Artifact 实例并传入 Runtime。"""
        db = _make_db()
        calls = []
        req = SessionCreateRequest(
            agent_type="test_generation",
            project_id=100,
            initial_artifacts=[
                {
                    "artifact_type": "user_intent",
                    "data": {"natural_language_request": "为登录流程生成测试用例"},
                }
            ],
        )

        with patch(_TARGET, side_effect=_runtime_factory(calls)):
            result = await run_session(
                req=req, db=db, current_user=MagicMock(id=7)
            )

        assert result["code"] == 200
        artifacts = calls[0]["initial_artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "user_intent"
        assert artifacts[0].natural_language_request == "为登录流程生成测试用例"


class TestRunSessionValidation:
    async def test_unregistered_artifact_returns_400(self, _no_perm_check):
        """未注册 artifact 类型 → AgentError → HTTP 400，且 Runtime 不被调用。"""
        db = _make_db()
        calls = []
        req = SessionCreateRequest(
            agent_type="test_generation",
            project_id=100,
            initial_artifacts=[{"artifact_type": "not_exist", "data": {}}],
        )

        with patch(_TARGET, side_effect=_runtime_factory(calls)):
            with pytest.raises(HTTPException) as exc:
                await run_session(req=req, db=db, current_user=MagicMock(id=7))

        assert exc.value.status_code == 400
        assert calls == []
        db.commit.assert_not_awaited()

    async def test_artifact_missing_type_returns_400(self, _no_perm_check):
        """缺 artifact_type → HTTP 400。"""
        db = _make_db()
        calls = []
        req = SessionCreateRequest(
            agent_type="test_generation",
            project_id=100,
            initial_artifacts=[{"data": {}}],
        )

        with patch(_TARGET, side_effect=_runtime_factory(calls)):
            with pytest.raises(HTTPException) as exc:
                await run_session(req=req, db=db, current_user=MagicMock(id=7))

        assert exc.value.status_code == 400
        assert calls == []


class TestRunSessionErrorHandling:
    async def test_runtime_exception_maps_to_500(self, _no_perm_check):
        """Runtime 抛通用异常 → HTTP 500，不冒泡为未处理错误。"""
        db = _make_db()
        req = SessionCreateRequest(agent_type="test_generation", project_id=100)

        with patch(
            _TARGET,
            side_effect=_runtime_factory([], raise_exc=RuntimeError("llm down")),
        ):
            with pytest.raises(HTTPException) as exc:
                await run_session(req=req, db=db, current_user=MagicMock(id=7))

        assert exc.value.status_code == 500

    async def test_agent_error_maps_to_400(self, _no_perm_check):
        """Runtime 抛 AgentError（如未注册 agent_type）→ HTTP 400。"""
        db = _make_db()
        req = SessionCreateRequest(agent_type="unknown_agent", project_id=100)

        with patch(
            _TARGET,
            side_effect=_runtime_factory(
                [], raise_exc=AgentError("未注册的 agent_type: unknown_agent")
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await run_session(req=req, db=db, current_user=MagicMock(id=7))

        assert exc.value.status_code == 400
