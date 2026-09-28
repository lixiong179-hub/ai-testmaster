"""TestGenerationAgent 端到端测试（Task 15 第二批）。

覆盖 8 个用例：definition 配置 / 全局注册 / CreateTestCaseTool 正常+异常 /
ValidateTestCaseSyntaxTool 校验 / 端到端流程 / run 无 runtime / 工具失败。

设计要点：
- 真实 async_db fixture 事务隔离，无 Mock 数据库；SessionService /
  AgentAuditService 真实调用，仅以薄适配器绑定 db 匹配 AgentRuntime
  调用约定（runtime 调 session_service.create_session(agent_type=...) 不传 db，
  而 SessionService.create_session(self, db, *, ...) 要求 db 位置参数）。
- LLM provider 为外部基础设施，按项目规则允许 Mock。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import select

from app.models.agent_audit import AgentAudit
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.test_case import TestCase, TestStep
from app.services.agent._registrations import register_default_agents
from app.services.agent.agents._test_case_tools import (
    CreateTestCaseTool,
    ValidateTestCaseSyntaxTool,
)
from app.services.agent.agents.test_generation_agent import TestGenerationAgent
from app.services.agent.artifacts.project_context_artifact import ProjectContextArtifact
from app.services.agent.artifacts.user_intent_artifact import UserIntentArtifact
from app.services.agent.audit_service import AgentAuditService
from app.services.agent.exceptions import ToolExecutionError
from app.services.agent.registry import get_global_registry
from app.services.agent.runtime import AgentRuntime
from app.services.agent.session_service import SessionService
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult
from app.services.agent.tools.registry import ToolRegistry


# ── Mock LLM provider（外部基础设施，按项目规则允许 Mock） ──


class MockLLMProvider:
    """按预置序列返回 LLM 响应，耗尽后返回无 tool_calls 的终止响应。"""

    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self._responses = responses
        self._index = 0
        self.calls: List[Dict[str, Any]] = []

    async def complete(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools})
        if self._index >= len(self._responses):
            return {"content": "完成", "tool_calls": [], "token_cost": 10}
        resp = self._responses[self._index]
        self._index += 1
        return resp


class _FinalAnswerTool(Tool):
    """final_answer 工具桩：终止会话并回传 summary。

    AgentRuntime 的 _check_termination 识别 final_answer 后终止循环，
    但 termination 检查发生在工具执行之后，故必须在 ToolRegistry 注册
    此工具，否则 _tool_executor 会抛 ToolExecutionError(工具未注册)。
    """

    name = "final_answer"
    description = "终止 Agent 会话并返回最终摘要"
    parameters_schema = {
        "type": "object",
        "properties": {
            "test_case_id": {"type": "integer"},
            "summary": {"type": "string"},
        },
        "required": ["summary"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(
            success=True,
            output={"test_case_id": params.get("test_case_id"), "summary": params.get("summary", "")},
        )


# ── db 绑定适配器：匹配 AgentRuntime 调用约定，真实委托服务逻辑（非 Mock） ──


class _DbBoundSessionService:
    """绑定 db 的 SessionService 适配器。

    AgentRuntime 调用 session_service.create_session(agent_type=...) 时不传 db，
    但 SessionService.create_session(self, db, *, ...) 要求 db 位置参数。
    本适配器持有 db 与真实 SessionService 实例，转发调用并注入 db，
    保证真实服务逻辑（校验/写入/flush）被完整执行。
    """

    def __init__(self, db: Any, service: SessionService) -> None:
        self._db = db
        self._service = service

    async def create_session(
        self, *, agent_type: str, project_id: int, created_by: Optional[int] = None,
    ) -> AgentSession:
        return await self._service.create_session(
            self._db, agent_type=agent_type, project_id=project_id, created_by=created_by,
        )

    async def append_message(
        self, *, session_id: int, role: str, content: dict,
        tool_name: Optional[str] = None, tool_call_id: Optional[str] = None,
        token_cost: int = 0,
    ) -> AgentMessage:
        return await self._service.append_message(
            self._db, session_id=session_id, role=role, content=content,
            tool_name=tool_name, tool_call_id=tool_call_id, token_cost=token_cost,
        )

    async def complete_session(
        self, *, session_id: int, status: str,
        token_cost: Optional[int] = None, iteration_count: Optional[int] = None,
        loop_detected: Optional[bool] = None,
    ) -> AgentSession:
        return await self._service.complete_session(
            self._db, session_id=session_id, status=status,
            token_cost=token_cost, iteration_count=iteration_count, loop_detected=loop_detected,
        )


class _DbBoundAuditService:
    """绑定 db 的 AgentAuditService 适配器（非 Mock，真实委托）。"""

    def __init__(self, db: Any, service: AgentAuditService) -> None:
        self._db = db
        self._service = service

    async def record_action(
        self, *, session_id: int, iteration: int, action_type: str,
        action_detail: dict, decision_confidence: Optional[float] = None,
    ) -> AgentAudit:
        return await self._service.record_action(
            self._db, session_id=session_id, iteration=iteration,
            action_type=action_type, action_detail=action_detail,
            decision_confidence=decision_confidence,
        )


def _make_tool_call(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构造 LLM 风格的 tool_call 字典。"""
    return {
        "id": f"call_{tool_name}",
        "function": {"name": tool_name, "arguments": json.dumps(args or {}, ensure_ascii=False)},
    }


def _build_runtime(
    async_db: Any, llm: MockLLMProvider, tool_registry: ToolRegistry,
    with_audit: bool = True,
) -> AgentRuntime:
    """构造真实 AgentRuntime：真实 SessionService/AgentAuditService 经适配器绑定 db。"""
    session_svc = _DbBoundSessionService(async_db, SessionService())
    audit_svc = _DbBoundAuditService(async_db, AgentAuditService()) if with_audit else None
    return AgentRuntime(
        db=async_db, llm_provider=llm,
        session_service=session_svc, audit_service=audit_svc,
        tool_registry=tool_registry, agent_registry=get_global_registry(),
    )


# ── 用例 1-2：definition 配置与全局注册 ──


class TestTestGenerationAgentDefinition:
    """TestGenerationAgent 配置正确性与全局注册。"""

    def test_definition_config(self) -> None:
        """用例1: definition 字段符合预期（6 工具 / None 预算）。"""
        defn = TestGenerationAgent.definition()
        assert defn.agent_type == "test_generation"
        assert "测试用例生成" in defn.system_prompt
        assert defn.tools == [
            "get_project_info", "query_similar_test_cases", "query_failure_history",
            "create_test_case", "validate_test_case_syntax", "final_answer",
        ]
        assert len(defn.tools) == 6
        assert defn.max_iterations is None
        assert defn.token_budget is None

    def test_registered_to_global_registry(self) -> None:
        """用例2: 已注册到全局 AgentRegistry。"""
        register_default_agents()  # 幂等，确保注册
        registry = get_global_registry()
        defn = registry.get("test_generation")
        assert defn is not None
        assert defn.agent_type == "test_generation"
        agent_types = [d.agent_type for d in registry.list_agents()]
        assert "test_generation" in agent_types


# ── 用例 3-4：CreateTestCaseTool 落库与异常 ──


class TestCreateTestCaseTool:
    """CreateTestCaseTool 正常落库与异常路径。"""

    async def test_execute_persists_case_and_steps(self, async_db, async_test_project) -> None:
        """用例3: 正常落库 → test_cases + test_steps 新增记录。"""
        tool = CreateTestCaseTool()
        context = ToolContext(db=async_db, project_id=async_test_project.id, agent_type="test_generation")
        params = {
            "project_id": async_test_project.id,
            "title": "登录-正常登录",
            "steps": [
                {"action": "navigate", "target": "登录页", "expected": "显示登录表单"},
                {"action": "input", "target": "用户名", "value": "testuser"},
                {"action": "click", "target": "登录按钮", "expected": "跳转首页"},
            ],
            "preconditions": ["用户已注册"],
            "priority": "high",
        }
        result = await tool.execute(params, context)
        assert result.success is True
        assert result.output["title"] == "登录-正常登录"
        case_id = result.output["test_case_id"]

        case = (await async_db.execute(
            select(TestCase).where(TestCase.id == case_id)
        )).scalar_one()
        assert case.title == "登录-正常登录"
        assert case.module == "AI生成"
        assert case.priority == 1
        assert case.case_type == "UI"

        steps = (await async_db.execute(
            select(TestStep).where(TestStep.test_case_id == case_id).order_by(TestStep.step_number)
        )).scalars().all()
        assert len(steps) == 3
        assert steps[0].action_type == "navigate"
        assert steps[1].action_type == "input"
        assert steps[2].action_type == "click"

    async def test_execute_invalid_project_id(self, async_db) -> None:
        """用例4a: 非法 project_id（不存在）→ ToolResult(success=False)。"""
        tool = CreateTestCaseTool()
        context = ToolContext(db=async_db, agent_type="test_generation")
        params = {"project_id": 999999, "title": "x", "steps": [{"action": "click"}]}
        result = await tool.execute(params, context)
        assert result.success is False
        assert result.error

    async def test_execute_missing_title(self, async_db, async_test_project) -> None:
        """用例4b: 缺失 title → KeyError 被 except 捕获 → ToolResult(success=False)。"""
        tool = CreateTestCaseTool()
        context = ToolContext(db=async_db, project_id=async_test_project.id, agent_type="test_generation")
        params = {"project_id": async_test_project.id, "steps": [{"action": "click"}]}
        result = await tool.execute(params, context)
        assert result.success is False
        assert result.error


# ── 用例 5：ValidateTestCaseSyntaxTool 校验 ──


class TestValidateTestCaseSyntaxTool:
    """ValidateTestCaseSyntaxTool 纯内存校验（不触及 DB）。"""

    async def test_validate_valid_steps(self) -> None:
        """用例5a: 合法 steps → valid=True, warnings=[]。"""
        tool = ValidateTestCaseSyntaxTool()
        result = await tool.execute(
            {"steps": [{"action": "click", "target": "btn"}, {"action": "input", "value": "x"}]},
            ToolContext(),
        )
        assert result.success is True
        assert result.output["valid"] is True
        assert result.output["warnings"] == []

    async def test_validate_missing_action(self) -> None:
        """用例5b: 缺 action 字段 → valid=False, warnings 含提示。"""
        tool = ValidateTestCaseSyntaxTool()
        result = await tool.execute({"steps": [{"target": "btn"}]}, ToolContext())
        assert result.success is True
        assert result.output["valid"] is False
        assert any("action" in w for w in result.output["warnings"])

    async def test_validate_invalid_action(self) -> None:
        """用例5c: 非法 action 值 → valid=False, warnings 含非法提示。"""
        tool = ValidateTestCaseSyntaxTool()
        result = await tool.execute({"steps": [{"action": "double_click"}]}, ToolContext())
        assert result.success is True
        assert result.output["valid"] is False
        assert any("非法" in w for w in result.output["warnings"])


# ── 用例 6-8：端到端流程与异常 ──


class TestTestGenerationAgentEndToEnd:
    """TestGenerationAgent 端到端流程。"""

    async def test_end_to_end_flow(self, async_db, async_test_project, async_test_user) -> None:
        """用例6: 真实 runtime 驱动 create_test_case → final_answer 全链路。"""
        register_default_agents()
        tool_registry = ToolRegistry()
        tool_registry.register(CreateTestCaseTool(), agent_types=["test_generation"])
        tool_registry.register(ValidateTestCaseSyntaxTool(), agent_types=["test_generation"])
        tool_registry.register(_FinalAnswerTool(), agent_types=["test_generation"])

        create_args = {
            "project_id": async_test_project.id,
            "title": "E2E-登录测试",
            "steps": [
                {"action": "navigate", "target": "登录页"},
                {"action": "click", "target": "登录按钮"},
            ],
            "priority": "medium",
        }
        llm = MockLLMProvider([
            {"content": "调用创建工具", "tool_calls": [_make_tool_call("create_test_case", create_args)], "token_cost": 50},
            {"content": "完成", "tool_calls": [_make_tool_call("final_answer", {"test_case_id": 1, "summary": "完成"})], "token_cost": 30},
        ])
        runtime = _build_runtime(async_db, llm, tool_registry)

        user_intent = UserIntentArtifact(
            natural_language_request="生成登录测试用例", constraints=["覆盖正向流程"],
        )
        project_context = ProjectContextArtifact(
            project_id=async_test_project.id, name=async_test_project.name,
            tech_stack=["Vue3"], base_url="http://test",
        )

        agent = TestGenerationAgent()
        session = await agent.run(
            artifacts=[user_intent, project_context], runtime=runtime, db=async_db,
            project_id=async_test_project.id, created_by=async_test_user.id,
        )
        assert session.status == "completed"
        assert session.iteration_count == 2

        # test_cases 落库
        cases = (await async_db.execute(
            select(TestCase).where(TestCase.project_id == async_test_project.id)
        )).scalars().all()
        assert any(c.title == "E2E-登录测试" for c in cases)

        # agent_sessions 落库
        db_session = await SessionService().get_session(async_db, session.id)
        assert db_session is not None
        assert db_session.status == "completed"
        assert db_session.agent_type == "test_generation"

        # agent_messages 含 assistant + tool（2 轮 × 2 条 = 4 条）
        msgs = await SessionService().get_history(async_db, session.id)
        roles = [m.role for m in msgs]
        assert "assistant" in roles
        assert "tool" in roles
        assert len(msgs) == 4

        # agent_audits 含 tool_call 审计（每轮工具调用一条）
        audits = await AgentAuditService().get_session_audit(async_db, session.id)
        assert len(audits) == 2
        assert all(a.action_type == "tool_call" for a in audits)

    async def test_run_without_runtime_raises_not_implemented(self) -> None:
        """用例7: run(runtime=None) → NotImplementedError。"""
        agent = TestGenerationAgent()
        with pytest.raises(NotImplementedError, match="runtime"):
            await agent.run(artifacts=[], runtime=None, db=None, project_id=1, created_by=1)

    async def test_run_tool_failure_marks_session_failed(
        self, async_db, async_test_project, async_test_user,
    ) -> None:
        """用例8: 工具未注册 → ToolExecutionError → session.status=failed。"""
        register_default_agents()
        tool_registry = ToolRegistry()  # 不注册 LLM 调用的工具 → 触发 ToolExecutionError
        llm = MockLLMProvider([
            {"content": "调用不存在工具", "tool_calls": [_make_tool_call("nonexistent_tool", {})], "token_cost": 10},
        ])
        runtime = _build_runtime(async_db, llm, tool_registry, with_audit=False)

        agent = TestGenerationAgent()
        with pytest.raises(ToolExecutionError) as exc_info:
            await agent.run(
                artifacts=[], runtime=runtime, db=async_db,
                project_id=async_test_project.id, created_by=async_test_user.id,
            )
        assert exc_info.value.tool_name == "nonexistent_tool"
        assert exc_info.value.session_id is not None

        db_session = await SessionService().get_session(async_db, exc_info.value.session_id)
        assert db_session is not None
        assert db_session.status == "failed"
