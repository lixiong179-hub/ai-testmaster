"""AgentRuntime 核心循环单元测试。

覆盖 10 个关键路径：正常完成 / 工具调用终止 / max_iterations 熔断 / loop 检测 /
token 超限 / circuit_breaker 阻断 / LLM 降级 / session 降级 / 工具异常 / metrics 埋点。

测试原则：LLM/loop_detector/circuit_breaker/token_guard/metrics 为外部基础设施使用 Mock；
session_service=None 时降级为内存 AgentSession，无需真实数据库。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from app.services.agent.base import AgentDefinition
from app.services.agent.exceptions import (
    AgentLoopDetected,
    CircuitBreakerOpen,
    MaxIterationsExceeded,
    TokenBudgetExceeded,
    ToolExecutionError,
)
from app.services.agent.registry import AgentRegistry
from app.services.agent.runtime import AgentRuntime
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult
from app.services.agent.tools.registry import ToolRegistry


# ── Mock 基础设施组件（外部依赖，按项目规则允许 Mock） ──


class MockLLMProvider:
    """Mock LLM provider，按预置序列返回响应。"""

    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self._responses = responses
        self._index = 0
        self.calls: List[Dict[str, Any]] = []

    async def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        self.calls.append({"messages": messages, "tools": tools})
        if self._index >= len(self._responses):
            raise RuntimeError("MockLLMProvider 响应已耗尽")
        resp = self._responses[self._index]
        self._index += 1
        return resp


class MockLoopDetector:
    """Mock 循环检测器。"""

    def __init__(self, detect: bool = False) -> None:
        self._detect = detect
        self.check_calls: List[Dict[str, Any]] = []

    @staticmethod
    def _build_signature(tool_name: str, args: Dict[str, Any]) -> str:
        return f"{tool_name}:{sorted(args.items())}"

    async def check(self, *, agent_type: str, session_id: Any, tool_call_signature: str) -> bool:
        self.check_calls.append({"agent_type": agent_type, "session_id": session_id, "signature": tool_call_signature})
        return self._detect


class MockCircuitBreaker:
    """Mock 熔断器。"""

    def __init__(self, allow: bool = True) -> None:
        self._allow = allow
        self.success_calls: List[str] = []
        self.failure_calls: List[str] = []

    async def allow(self, agent_type: str) -> bool:
        return self._allow

    async def record_success(self, agent_type: str) -> None:
        self.success_calls.append(agent_type)

    async def record_failure(self, agent_type: str) -> None:
        self.failure_calls.append(agent_type)


class MockTokenGuard:
    """Mock Token 预算守卫。"""

    def __init__(self, exhausted: bool = False) -> None:
        self._exhausted = exhausted
        self.consumed: List[int] = []

    def is_daily_budget_exhausted(self) -> bool:
        return self._exhausted

    def consume(self, amount: int) -> None:
        self.consumed.append(amount)


class MockMetrics:
    """Mock 指标埋点。"""

    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def record_session_start(self, agent_type: str) -> None:
        self.calls.append(("record_session_start", agent_type))

    def record_iteration(self, agent_type: str, duration: float) -> None:
        self.calls.append(("record_iteration", agent_type, duration))

    def record_session_end(self, agent_type: str, status: str, duration: float, token_cost: int) -> None:
        self.calls.append(("record_session_end", agent_type, status, duration, token_cost))

    def record_circuit_breaker_state(self, agent_type: str, state: str) -> None:
        self.calls.append(("record_circuit_breaker_state", agent_type, state))

    def record_loop_detected(self, agent_type: str) -> None:
        self.calls.append(("record_loop_detected", agent_type))

    def record_tool_call(self, tool_name: str, success: bool) -> None:
        self.calls.append(("record_tool_call", tool_name, success))


# ── 测试用工具 ──


class _NoopTool(Tool):
    name = "noop_tool"
    description = "test noop tool"
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(success=True, output={"echo": "ok"})


class _ErrorTool(Tool):
    name = "error_tool"
    description = "test error tool"
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        raise RuntimeError("tool boom")


class _FinalAnswerTool(Tool):
    name = "final_answer"
    description = "final answer tool"
    parameters_schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(success=True, output={"answer": params.get("answer", "")})


def _make_tool_call(tool_name: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """构造 LLM 风格的 tool_call 字典。"""
    args = args or {}
    return {"id": f"call_{tool_name}", "function": {"name": tool_name, "arguments": json.dumps(args)}}


# ── Fixtures ──


@pytest.fixture
def test_agent_definition() -> AgentDefinition:
    return AgentDefinition(
        agent_type="test_agent",
        system_prompt="你是测试 Agent",
        tools=["final_answer", "noop_tool"],
        max_iterations=3,
    )


@pytest.fixture
def runtime_with_test_agent(test_agent_definition: AgentDefinition) -> AgentRuntime:
    """独立 AgentRegistry，避免污染全局注册表。"""
    registry = AgentRegistry()
    registry.register(test_agent_definition)
    return AgentRuntime(agent_registry=registry)


@pytest.fixture
def tool_registry_with_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_NoopTool())
    registry.register(_ErrorTool())
    registry.register(_FinalAnswerTool())
    return registry


# ── 测试用例 ──


async def test_run_completes_when_no_tool_calls(runtime_with_test_agent: AgentRuntime) -> None:
    """用例1: LLM 返回无 tool_calls → 立即终止 → status="completed"。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "任务完成", "tool_calls": [], "token_cost": 100},
    ])
    session = await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert session.status == "completed"
    assert session.iteration_count == 1
    assert session.token_cost == 100


async def test_run_with_tool_calls_then_final_answer(
    runtime_with_test_agent: AgentRuntime,
    tool_registry_with_tools: ToolRegistry,
) -> None:
    """用例2: LLM 返回 tool_calls → 执行工具 → final_answer 终止。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "调用工具", "tool_calls": [_make_tool_call("noop_tool")], "token_cost": 50},
        {"content": "最终答案", "tool_calls": [_make_tool_call("final_answer", {"answer": "done"})], "token_cost": 60},
    ])
    runtime_with_test_agent.tool_registry = tool_registry_with_tools
    session = await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert session.status == "completed"
    assert session.iteration_count == 2
    assert session.token_cost == 110


async def test_run_raises_max_iterations(
    runtime_with_test_agent: AgentRuntime,
    tool_registry_with_tools: ToolRegistry,
) -> None:
    """用例3: 持续返回 tool_calls 不终止 → 抛 MaxIterationsExceeded。"""
    responses = [
        {"content": f"iter {i}", "tool_calls": [_make_tool_call("noop_tool")], "token_cost": 10}
        for i in range(3)
    ]
    runtime_with_test_agent.llm_provider = MockLLMProvider(responses)
    runtime_with_test_agent.tool_registry = tool_registry_with_tools
    with pytest.raises(MaxIterationsExceeded) as exc_info:
        await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert exc_info.value.agent_type == "test_agent"


async def test_run_raises_loop_detected(
    runtime_with_test_agent: AgentRuntime,
    tool_registry_with_tools: ToolRegistry,
) -> None:
    """用例4: 第二轮 _check_loop 检测到重复签名 → 抛 AgentLoopDetected。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "调用工具", "tool_calls": [_make_tool_call("noop_tool")], "token_cost": 50},
        {"content": "再次调用", "tool_calls": [_make_tool_call("noop_tool")], "token_cost": 50},
    ])
    loop_detector = MockLoopDetector(detect=True)
    runtime_with_test_agent.loop_detector = loop_detector
    runtime_with_test_agent.tool_registry = tool_registry_with_tools
    with pytest.raises(AgentLoopDetected):
        await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert len(loop_detector.check_calls) >= 1


async def test_run_raises_token_budget_exhausted(runtime_with_test_agent: AgentRuntime) -> None:
    """用例5: token_guard.is_daily_budget_exhausted=True → 抛 TokenBudgetExceeded。"""
    runtime_with_test_agent.token_guard = MockTokenGuard(exhausted=True)
    with pytest.raises(TokenBudgetExceeded):
        await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])


async def test_run_raises_circuit_breaker_open(runtime_with_test_agent: AgentRuntime) -> None:
    """用例6: circuit_breaker.allow=False → 抛 CircuitBreakerOpen。"""
    runtime_with_test_agent.circuit_breaker = MockCircuitBreaker(allow=False)
    with pytest.raises(CircuitBreakerOpen):
        await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])


async def test_run_degrades_when_llm_provider_none(runtime_with_test_agent: AgentRuntime) -> None:
    """用例7: llm_provider=None → 返回 "LLM provider 不可用" 立即终止。"""
    session = await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert session.status == "completed"
    assert session.iteration_count == 1
    assert session.token_cost == 0


async def test_run_uses_in_memory_session_when_session_service_none(
    runtime_with_test_agent: AgentRuntime,
) -> None:
    """用例8: session_service=None → 使用内存 AgentSession（id=None）。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "完成", "tool_calls": [], "token_cost": 0},
    ])
    session = await runtime_with_test_agent.run(
        agent_type="test_agent", project_id=42, initial_artifacts=[], created_by=99,
    )
    assert session.id is None
    assert session.project_id == 42
    assert session.agent_type == "test_agent"
    assert session.created_by == 99
    assert session.status == "completed"


async def test_run_wraps_tool_exception_as_tool_execution_error(
    runtime_with_test_agent: AgentRuntime,
    tool_registry_with_tools: ToolRegistry,
) -> None:
    """用例9: 工具抛异常 → 包装为 ToolExecutionError → session.status="failed"。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "调用错误工具", "tool_calls": [_make_tool_call("error_tool")], "token_cost": 50},
    ])
    runtime_with_test_agent.tool_registry = tool_registry_with_tools
    with pytest.raises(ToolExecutionError) as exc_info:
        await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    assert exc_info.value.tool_name == "error_tool"
    assert exc_info.value.agent_type == "test_agent"


async def test_run_records_metrics(runtime_with_test_agent: AgentRuntime) -> None:
    """用例10: metrics 提供时，record_session_start/record_iteration/record_session_end 被调用。"""
    runtime_with_test_agent.llm_provider = MockLLMProvider([
        {"content": "完成", "tool_calls": [], "token_cost": 100},
    ])
    metrics = MockMetrics()
    runtime_with_test_agent.metrics = metrics
    await runtime_with_test_agent.run(agent_type="test_agent", project_id=1, initial_artifacts=[])
    call_types = [c[0] for c in metrics.calls]
    assert "record_session_start" in call_types
    assert "record_iteration" in call_types
    assert "record_session_end" in call_types
    end_calls = [c for c in metrics.calls if c[0] == "record_session_end"]
    assert len(end_calls) == 1
    assert end_calls[0][2] == "completed"
    assert end_calls[0][4] == 100
