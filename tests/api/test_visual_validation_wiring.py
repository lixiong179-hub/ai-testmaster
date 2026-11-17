"""R3-3 视觉校验接线验收（Q4 = 按项目配置、默认关）。

覆盖双路径：
    - 开：全局 + 项目开关均开启 → 执行链路触发管线，新增 1 条
      `agent_sessions`（agent_type=visual_validation）
    - 关：全局关（零查询、零会话）/ 项目关（不触发）

测试策略与 R1-1 接线测试一致：直接 await 端点函数（单元风格），
`asyncio.create_task` 替换为「收集协程」的同步钩子，使 fire-and-forget
的后台逻辑可被显式 await 后断言。
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.endpoints.execution_core import analyze_failure
from app.api.v1.endpoints.report import _load_visual_validation_summary
from app.core.config import settings
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.enums import ExecStatus
from app.models.project import Project
from app.services.agent.session_service import SessionService
from app.services.visual_validation import is_visual_validation_enabled
from app.services.visual_validation.service import spawn_visual_validation_agent

_EP = "app.api.v1.endpoints.execution_core"
_SESSION_LOCAL = "app.db.database.AsyncPrimarySessionLocal"
_RUNTIME = "app.services.agent.runtime.AgentRuntime"


# ============================================================================
# 替身与辅助
# ============================================================================


def _scalar_result(value):
    """构造 `scalar_one_or_none()` 查询结果替身。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.first.return_value = value
    return result


def _query_result(scalar_value, rows=()):
    """构造同时支持 `scalar_one_or_none()` 与 `scalars().all()` 的查询替身。"""
    query = MagicMock()
    query.scalar_one_or_none.return_value = scalar_value
    query.scalars.return_value.all.return_value = list(rows)
    return query


def _make_db(execute_results):
    """构造 AsyncSession 替身：execute 按序返回预置结果。"""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute_results)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _make_sync_db(execute_results):
    """构造同步 Session 替身（R2-1：端点已切 `Depends(get_db)`）：execute 按序返回预置结果。"""
    db = MagicMock()
    db.execute = MagicMock(side_effect=execute_results)
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


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


class _AsyncDBWrapper:
    """把同步测试库包装成 Agent 会话服务所需的最小 AsyncSession。

    `SessionService.create_session` 仅使用 `add/flush/refresh`，此处按需代理，
    使「真实编排器 + 真实会话服务」能把会话写进测试事务。
    """

    def __init__(self, sync_db):
        self._db = sync_db

    def add(self, obj):
        return self._db.add(obj)

    async def flush(self):
        self._db.flush()

    async def refresh(self, obj):
        self._db.refresh(obj)

    async def commit(self):
        self._db.flush()

    async def execute(self, stmt):
        """代理同步查询（测试事务内读取真实数据）。"""
        return self._db.execute(stmt)


class _FakeSessionFactory:
    """`AsyncPrimarySessionLocal` 替身：支持 `async with`。"""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *exc_info):
        return False


class _StubAgentRuntime:
    """AgentRuntime 替身：真实创建 AgentSession 行（不调用 LLM）。"""

    def __init__(self, db=None, **kwargs):
        self._db = db

    async def run(
        self,
        agent_type,
        project_id,
        initial_artifacts,
        execution_callback=None,
        created_by=None,
    ):
        return await SessionService().create_session(
            self._db,
            agent_type=agent_type,
            project_id=project_id,
            created_by=created_by,
        )


def _capture_task(captured):
    """同步钩子：收集协程并返回假 task（随后由测试显式 await）。"""

    def _hook(coro):
        captured.append(coro)
        return MagicMock()

    return _hook


def _count_visual_sessions(db, project_id: int) -> int:
    return (
        db.query(AgentSession)
        .filter(
            AgentSession.project_id == project_id,
            AgentSession.agent_type == "visual_validation",
        )
        .count()
    )


# ============================================================================
# 开关判定
# ============================================================================


class TestVisualValidationGate:
    """全局关 = 零查询；项目关 = 不触发。"""

    async def test_global_disabled_returns_false_without_query(self, monkeypatch):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", False)
        db = MagicMock()
        db.execute = AsyncMock()

        assert await is_visual_validation_enabled(db, 100) is False
        db.execute.assert_not_awaited()

    async def test_project_disabled_returns_false(self, monkeypatch):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", True)
        db = _make_db([_scalar_result({"visual_validation_config": {"enabled": False}})])

        assert await is_visual_validation_enabled(db, 100) is False

    async def test_project_and_global_enabled_returns_true(self, monkeypatch):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", True)
        db = _make_db([_scalar_result({"visual_validation_config": {"enabled": True}})])

        assert await is_visual_validation_enabled(db, 100) is True

    async def test_project_config_absent_defaults_to_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", True)
        db = _make_db([_scalar_result(None)])

        assert await is_visual_validation_enabled(db, 100) is True


# ============================================================================
# 端点接线：开 → 触发；关 → 不触发
# ============================================================================


class TestExecutionCoreWiring:
    """失败分析路径按开关触发视觉校验。"""

    async def test_enabled_triggers_visual_validation(self, monkeypatch):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", True)
        db = _make_sync_db([
            _query_result(_failed_result()),
            _query_result(_test_case()),
            _query_result(None, []),
        ])
        user = MagicMock(id=7)

        with (
            patch(f"{_EP}._get_hidden_fields", new=MagicMock(return_value=[])),
            patch(f"{_EP}._spawn_failure_analysis_agent"),
            patch(
                f"{_EP}.is_visual_validation_enabled_sync",
                new=MagicMock(return_value=True),
            ),
            patch(f"{_EP}.spawn_visual_validation_agent") as spawn,
        ):
            resp = await analyze_failure(result_id=999, db=db, current_user=user)

        assert resp["code"] == 200
        spawn.assert_called_once()
        kwargs = spawn.call_args.kwargs
        assert kwargs["project_id"] == 100
        assert kwargs["created_by"] == 7
        assert kwargs["last_error"] == "element not found"

    async def test_disabled_does_not_trigger_visual_validation(
        self, monkeypatch, db, testUser
    ):
        monkeypatch.setattr(settings, "AI_VISUAL_VALIDATION_ENABLED", False)
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)
        suffix = uuid.uuid4().hex[:8]
        project = Project(
            name=f"vv_off_{suffix}",
            user_id=testUser.id,
            description="视觉校验关闭路径",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()

        mock_db = _make_sync_db([
            _query_result(_failed_result()),
            _query_result(_test_case(project_id=project.id)),
            _query_result(None, []),
        ])
        user = MagicMock(id=7)

        with (
            patch(f"{_EP}._get_hidden_fields", new=MagicMock(return_value=[])),
            patch(f"{_EP}._spawn_failure_analysis_agent"),
            patch(f"{_EP}.spawn_visual_validation_agent") as spawn,
        ):
            resp = await analyze_failure(result_id=999, db=mock_db, current_user=user)

        assert resp["code"] == 200
        spawn.assert_not_called()
        assert _count_visual_sessions(db, project.id) == 0


# ============================================================================
# 触发实现：开 → 新增 1 条 agent_sessions
# ============================================================================


class TestSpawnCreatesSession:
    """spawn 在独立会话中执行管线并由会话服务落库。"""

    async def test_spawn_creates_single_visual_validation_session(self, db, testUser):
        suffix = uuid.uuid4().hex[:8]
        project = Project(
            name=f"vv_on_{suffix}",
            user_id=testUser.id,
            description="视觉校验开启路径",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()

        captured = []
        with (
            patch(_SESSION_LOCAL, new=_FakeSessionFactory(_AsyncDBWrapper(db))),
            patch(_RUNTIME, new=_StubAgentRuntime),
            patch("asyncio.create_task", new=_capture_task(captured)),
        ):
            spawn_visual_validation_agent(
                project_id=project.id,
                created_by=testUser.id,
                screenshot_url="https://cdn.example.com/a.png",
                last_error="element not found",
            )
            assert len(captured) == 1
            await captured[0]

        assert _count_visual_sessions(db, project.id) == 1
        session = (
            db.query(AgentSession)
            .filter(AgentSession.project_id == project.id)
            .first()
        )
        assert session.agent_type == "visual_validation"
        assert session.created_by == testUser.id


# ============================================================================
# 报告输出：结论与截图引用
# ============================================================================


class TestReportVisualSection:
    """报告详情附加视觉校验结论与截图引用。"""

    async def test_report_summary_reads_conclusion_and_screenshot(self, db, testUser):
        suffix = uuid.uuid4().hex[:8]
        project = Project(
            name=f"vv_report_{suffix}",
            user_id=testUser.id,
            description="视觉校验报告",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()

        session = AgentSession(
            project_id=project.id,
            agent_type="visual_validation",
            status="completed",
            token_cost=180,
            iteration_count=2,
            loop_detected=False,
            created_by=testUser.id,
        )
        db.add(session)
        db.flush()

        db.add(
            AgentMessage(
                session_id=session.id,
                role="assistant",
                content={
                    "arguments": json.dumps(
                        {"conclusion": "差异 6.2%，判定为视觉回归缺陷"},
                        ensure_ascii=False,
                    )
                },
                tool_name="final_answer",
                token_cost=0,
            )
        )
        db.flush()

        summary = await _load_visual_validation_summary(
            _AsyncDBWrapper(db), project.id
        )

        assert summary is not None
        assert summary["session_id"] == session.id
        assert summary["status"] == "completed"
        assert summary["conclusion"] == "差异 6.2%，判定为视觉回归缺陷"
        assert summary["screenshot_url"] is None
