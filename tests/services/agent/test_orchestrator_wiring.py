"""R1-1: AgentOrchestrator 接入失败分析链路的接线测试。

接线点：`app/api/v1/endpoints/execution_core/_analysis.py`
  - `analyze_failure`（@L59 附近）在脱敏后调用 `_spawn_failure_analysis_agent`
  - `_spawn_failure_analysis_agent` 以 fire-and-forget 方式在**独立会话**中
    执行 `AgentOrchestrator.execute_pipeline(pipeline=["failure_analysis"], ...)`

测试策略：直接 await 端点函数（单元风格），规避 O-13 所述的「每个 pytest 会话首个
HTTP 测试必失败」。`asyncio.create_task` 被替换为「收集协程」的钩子，使
fire-and-forget 的后台逻辑可被同步断言。

覆盖：
    - 触发：analyze_failure 在返回 200 前调用 _spawn_failure_analysis_agent，参数正确
    - 不阻塞：端点立即返回既有响应体（Agent 结果不混入响应）
    - 编排执行：_spawn 内部构造 AgentOrchestrator 并执行 failure_analysis 管线
    - 异常隔离：编排抛异常时 _spawn 仅告警，不向外抛出
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.execution_core._analysis import (
    _spawn_failure_analysis_agent,
    analyze_failure,
)
from app.models.enums import ExecStatus

_ANALYSIS = "app.api.v1.endpoints.execution_core._analysis"
_ORCHESTRATOR = "app.services.agent.orchestrator.AgentOrchestrator"
_SESSION_LOCAL = "app.db.database.AsyncPrimarySessionLocal"


def _make_db(execute_results):
    """构造 AsyncSession 替身：execute 按序返回预置结果。"""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute_results)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _query_result(scalar_value, rows=()):
    """构造同时支持 scalar_one_or_none() 与 scalars().all() 的查询替身。"""
    query = MagicMock()
    query.scalar_one_or_none.return_value = scalar_value
    query.scalars.return_value.all.return_value = list(rows)
    return query


def _failed_result(case_id=321, error_msg="element not found"):
    result = MagicMock()
    result.id = 999
    result.case_id = case_id
    result.exec_status = ExecStatus.FAILED
    result.error_msg = error_msg
    result.ai_analysis = "定位失败"
    return result


def _test_case(project_id=100, case_id=321):
    test_case = MagicMock()
    test_case.id = case_id
    test_case.project_id = project_id
    test_case.is_deleted = False
    test_case.title = "登录流程"
    test_case.precondition = None
    test_case.steps_json = []
    return test_case


class _FakeSessionFactory:
    """AsyncPrimarySessionLocal 替身：支持 async with。"""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *exc_info):
        return False


class TestAnalyzeFailureTriggersAgent:
    async def test_analyze_failure_spawns_agent_with_correct_args(self):
        """analyze_failure 在返回前触发后台 Agent，参数来自执行结果与用例。"""
        result = _failed_result()
        test_case = _test_case()
        db = _make_db([_query_result(result), _query_result(test_case), _query_result(None, [])])
        user = MagicMock(id=7)

        with patch(f"{_ANALYSIS}._get_hidden_fields_async", new=AsyncMock(return_value=[])):
            with patch(f"{_ANALYSIS}._spawn_failure_analysis_agent") as spawn:
                resp = await analyze_failure(
                    result_id=999, db=db, current_user=user
                )

        # 1) 端点仍返回既有 200 响应（Agent 结果不混入响应体）
        assert resp["code"] == 200
        assert resp["data"]["result_id"] == 999

        # 2) 后台 Agent 被触发，参数正确
        spawn.assert_called_once()
        kwargs = spawn.call_args.kwargs
        assert kwargs["project_id"] == 100
        assert kwargs["created_by"] == 7
        assert kwargs["last_error"] == "element not found"

    async def test_non_failed_result_does_not_spawn_agent(self):
        """非 FAILED 结果直接 400，不触发 Agent。"""
        result = _failed_result()
        result.exec_status = ExecStatus.PASSED
        db = _make_db([_query_result(result)])
        user = MagicMock(id=7)

        from fastapi import HTTPException

        with patch(f"{_ANALYSIS}._spawn_failure_analysis_agent") as spawn:
            with pytest.raises(HTTPException) as exc:
                await analyze_failure(result_id=999, db=db, current_user=user)

        assert exc.value.status_code == 400
        spawn.assert_not_called()


class TestSpawnFailureAnalysisAgent:
    async def test_spawn_executes_failure_analysis_pipeline(self):
        """_spawn 在独立会话中构造编排器并执行 failure_analysis 管线。"""
        db = MagicMock()
        db.commit = AsyncMock()
        orchestrator = MagicMock()
        orchestrator.execute_pipeline = AsyncMock(return_value=MagicMock())

        captured = []

        def _capture(coro):
            """同步钩子：收集协程并返回一个假的 task（随后由测试显式 await）。"""
            captured.append(coro)
            return MagicMock()

        with patch(_SESSION_LOCAL, new=_FakeSessionFactory(db)):
            with patch(_ORCHESTRATOR, return_value=orchestrator):
                with patch("asyncio.create_task", new=_capture):
                    _spawn_failure_analysis_agent(
                        project_id=100,
                        created_by=7,
                        last_error="element not found",
                        screenshot_url=None,
                    )

                    # 必须在 patch 上下文内 await —— _spawn 内部为延迟导入，
                    # 退出补丁后再执行会拿到真实的 AgentOrchestrator。
                    assert len(captured) == 1
                    await captured[0]

        orchestrator.execute_pipeline.assert_awaited_once()
        kwargs = orchestrator.execute_pipeline.await_args.kwargs
        assert kwargs["pipeline"] == ["failure_analysis"]
        assert kwargs["project_id"] == 100
        assert kwargs["created_by"] == 7
        # artifact 注入
        artifacts = kwargs["initial_artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "execution_state"
        assert artifacts[0].last_error == "element not found"
        db.commit.assert_awaited_once()

    async def test_spawn_isolates_exceptions(self):
        """编排抛异常时 _spawn 仅告警，不向外抛出。"""
        db = MagicMock()
        db.commit = AsyncMock()
        orchestrator = MagicMock()
        orchestrator.execute_pipeline = AsyncMock(side_effect=RuntimeError("llm down"))

        captured = []

        def _capture(coro):
            """同步钩子：收集协程并返回一个假的 task（随后由测试显式 await）。"""
            captured.append(coro)
            return MagicMock()

        with patch(_SESSION_LOCAL, new=_FakeSessionFactory(db)):
            with patch(_ORCHESTRATOR, return_value=orchestrator):
                with patch("asyncio.create_task", new=_capture):
                    _spawn_failure_analysis_agent(
                        project_id=100, created_by=7,
                        last_error="boom", screenshot_url=None,
                    )

                    # 关键断言：await 后台协程不抛异常 —— 异常已被隔离为 warning
                    await captured[0]

        orchestrator.execute_pipeline.assert_awaited_once()
        db.commit.assert_not_awaited()
