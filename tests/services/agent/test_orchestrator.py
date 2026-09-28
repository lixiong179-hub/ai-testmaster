"""AgentOrchestrator 单元测试。

覆盖 18 个关键路径：
    1. 正常完成：4 Agent 全部成功 → COMPLETED
    2. 空 pipeline 抛 AgentError
    3. 未注册 Agent 抛 AgentError
    4. 禁用 Agent 抛 AgentError
    5. stop_on_failure=True 单步失败立即终止 → FAILED
    6. stop_on_failure=False 单步失败继续执行 → PARTIAL
    7. 全部失败 + stop_on_failure=False → PARTIAL
    8. 中间失败 + stop_on_failure=False 后续步骤继续执行
    9. _merge_artifacts 同类型 new 覆盖 base
    10. _merge_artifacts 不同类型并存
    11. artifact 累积传递：后续 Agent 接收前序累积 artifacts
    12. execution_callback 透传到每个 Agent
    13. created_by 透传到每个 Agent
    14. pipeline_id 为 UUID 字符串
    15. total_token_cost 与 total_duration_seconds 累加正确
    16. _extract_output_artifacts 处理空 final_answer
    17. _extract_output_artifacts 处理非 JSON / 非 dict final_answer
    18. 自定义 agent_registry 注入生效

测试原则：AgentRuntime 通过 MockRuntime 替换，不依赖真实 LLM/DB/工具系统。
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.services.agent.artifacts.base import Artifact
from app.services.agent.artifacts.project_context_artifact import (
    ProjectContextArtifact,
)
from app.services.agent.artifacts.user_intent_artifact import UserIntentArtifact
from app.services.agent.base import AgentDefinition
from app.services.agent.exceptions import AgentError
from app.services.agent.orchestrator import (
    AgentOrchestrator,
    OrchestrationResult,
    PipelineStatus,
    PipelineStepResult,
)
from app.services.agent.registry import AgentRegistry


# ── Mock 基础设施 ──


class _MockSession:
    """内存 AgentSession 替身，仅暴露 orchestrator 访问的字段。"""

    def __init__(
        self,
        session_id: int,
        token_cost: int = 100,
        final_answer: str = "",
        status: str = "completed",
    ) -> None:
        self.id = session_id
        self.token_cost = token_cost
        self.final_answer = final_answer
        self.status = status


class MockRuntime:
    """Mock AgentRuntime，按预置脚本返回 session 或抛异常。

    用法：
        runtime = MockRuntime()
        runtime.enqueue_session(_MockSession(1, token_cost=50))
        runtime.enqueue_failure(RuntimeError("boom"))
        # 调用 run() 时按入队顺序消费
    """

    def __init__(self) -> None:
        self._queue: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, Any]] = []

    def enqueue_session(
        self,
        session_id: int,
        token_cost: int = 100,
        final_answer: str = "",
        status: str = "completed",
    ) -> None:
        """入队一个成功 session。"""
        self._queue.append(
            {
                "type": "session",
                "session": _MockSession(
                    session_id=session_id,
                    token_cost=token_cost,
                    final_answer=final_answer,
                    status=status,
                ),
            }
        )

    def enqueue_failure(self, exc: BaseException) -> None:
        """入队一个失败（run 调用时抛出指定异常）。"""
        self._queue.append({"type": "failure", "exc": exc})

    async def run(
        self,
        agent_type: str,
        project_id: int,
        initial_artifacts: List[Artifact],
        execution_callback: Optional[Any] = None,
        created_by: Optional[int] = None,
    ) -> Any:
        """记录调用参数并按队列返回结果。"""
        self.calls.append(
            {
                "agent_type": agent_type,
                "project_id": project_id,
                "initial_artifacts": list(initial_artifacts),
                "execution_callback": execution_callback,
                "created_by": created_by,
            }
        )
        if not self._queue:
            raise RuntimeError("MockRuntime 队列为空")
        item = self._queue.pop(0)
        if item["type"] == "failure":
            raise item["exc"]
        return item["session"]


# ── Fixtures ──


def _make_definition(agent_type: str) -> AgentDefinition:
    """构造测试用 AgentDefinition。"""
    return AgentDefinition(
        agent_type=agent_type,
        system_prompt=f"你是 {agent_type} 测试 Agent",
        tools=["final_answer"],
        max_iterations=3,
    )


@pytest.fixture
def four_agent_registry() -> AgentRegistry:
    """独立 AgentRegistry，注册 4 个测试 Agent，避免污染全局注册表。"""
    registry = AgentRegistry()
    for agent_type in (
        "test_generation",
        "test_execution",
        "failure_analysis",
        "locator_healing",
    ):
        registry.register(_make_definition(agent_type))
    return registry


@pytest.fixture
def runtime() -> MockRuntime:
    return MockRuntime()


@pytest.fixture
def orchestrator(
    runtime: MockRuntime,
    four_agent_registry: AgentRegistry,
) -> AgentOrchestrator:
    """注入 MockRuntime 与独立 AgentRegistry 的编排器。"""
    return AgentOrchestrator(
        runtime=runtime,  # type: ignore[arg-type]
        agent_registry=four_agent_registry,
    )


@pytest.fixture
def initial_artifacts() -> List[Artifact]:
    """初始 artifacts：user_intent + project_context。"""
    return [
        UserIntentArtifact(natural_language_request="生成登录功能测试用例"),
        ProjectContextArtifact(project_id=1, name="demo-app", base_url="http://localhost:8080"),
    ]


# ── 测试用例 ──


async def test_execute_pipeline_completes_when_all_agents_succeed(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例1: 4 个 Agent 全部成功 → status=COMPLETED，steps 全部 completed。"""
    runtime.enqueue_session(session_id=101, token_cost=50)
    runtime.enqueue_session(session_id=102, token_cost=60)
    runtime.enqueue_session(session_id=103, token_cost=70)
    runtime.enqueue_session(session_id=104, token_cost=80)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis", "locator_healing"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        created_by=42,
    )

    assert result.status == PipelineStatus.COMPLETED
    assert len(result.steps) == 4
    assert [s.status for s in result.steps] == ["completed"] * 4
    assert [s.session_id for s in result.steps] == [101, 102, 103, 104]
    assert result.total_token_cost == 50 + 60 + 70 + 80
    assert result.total_duration_seconds >= 0.0
    assert len(runtime.calls) == 4


async def test_execute_pipeline_raises_on_empty_pipeline(
    orchestrator: AgentOrchestrator,
    initial_artifacts: List[Artifact],
) -> None:
    """用例2: pipeline 为空 → 抛 AgentError。"""
    with pytest.raises(AgentError) as exc_info:
        await orchestrator.execute_pipeline(
            pipeline=[],
            project_id=1,
            initial_artifacts=initial_artifacts,
        )
    assert "pipeline 不能为空" in str(exc_info.value)


async def test_execute_pipeline_raises_on_unregistered_agent(
    orchestrator: AgentOrchestrator,
    initial_artifacts: List[Artifact],
) -> None:
    """用例3: pipeline 包含未注册的 agent_type → 抛 AgentError。"""
    with pytest.raises(AgentError) as exc_info:
        await orchestrator.execute_pipeline(
            pipeline=["unknown_agent"],
            project_id=1,
            initial_artifacts=initial_artifacts,
        )
    assert "未注册" in str(exc_info.value)
    assert exc_info.value.agent_type == "unknown_agent"


async def test_execute_pipeline_raises_on_disabled_agent(
    orchestrator: AgentOrchestrator,
    four_agent_registry: AgentRegistry,
    initial_artifacts: List[Artifact],
) -> None:
    """用例4: pipeline 包含已禁用的 agent_type → 抛 AgentError。"""
    four_agent_registry.disable("test_generation")
    with pytest.raises(AgentError) as exc_info:
        await orchestrator.execute_pipeline(
            pipeline=["test_generation"],
            project_id=1,
            initial_artifacts=initial_artifacts,
        )
    assert "已禁用" in str(exc_info.value)
    assert exc_info.value.agent_type == "test_generation"


async def test_execute_pipeline_stops_on_failure_when_stop_on_failure_true(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例5: stop_on_failure=True 时首步失败立即终止 → status=FAILED，仅执行 1 步。"""
    runtime.enqueue_failure(RuntimeError("agent boom"))

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        stop_on_failure=True,
    )

    assert result.status == PipelineStatus.FAILED
    assert len(result.steps) == 1
    assert result.steps[0].status == "failed"
    assert result.steps[0].session_id is None
    assert "agent boom" in result.steps[0].error
    assert result.steps[0].token_cost == 0
    assert len(runtime.calls) == 1  # 后续 Agent 未被调用


async def test_execute_pipeline_continues_on_failure_when_stop_on_failure_false(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例6: stop_on_failure=False 时首步失败继续执行 → status=PARTIAL。"""
    runtime.enqueue_failure(RuntimeError("first boom"))
    runtime.enqueue_session(session_id=201, token_cost=30)
    runtime.enqueue_session(session_id=202, token_cost=40)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        stop_on_failure=False,
    )

    assert result.status == PipelineStatus.PARTIAL
    assert len(result.steps) == 3
    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "completed"
    assert result.steps[2].status == "completed"
    assert result.total_token_cost == 30 + 40
    assert len(runtime.calls) == 3


async def test_execute_pipeline_all_failed_with_stop_on_failure_false(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例7: 全部失败 + stop_on_failure=False → status=PARTIAL，所有 step failed。"""
    runtime.enqueue_failure(RuntimeError("e1"))
    runtime.enqueue_failure(RuntimeError("e2"))
    runtime.enqueue_failure(RuntimeError("e3"))

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        stop_on_failure=False,
    )

    assert result.status == PipelineStatus.PARTIAL
    assert len(result.steps) == 3
    assert [s.status for s in result.steps] == ["failed", "failed", "failed"]
    assert result.total_token_cost == 0


async def test_execute_pipeline_middle_failure_continues_with_stop_on_failure_false(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例8: 中间步骤失败 + stop_on_failure=False → 后续步骤继续执行。"""
    runtime.enqueue_session(session_id=301, token_cost=10)
    runtime.enqueue_failure(RuntimeError("middle boom"))
    runtime.enqueue_session(session_id=302, token_cost=20)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        stop_on_failure=False,
    )

    assert result.status == PipelineStatus.PARTIAL
    assert [s.status for s in result.steps] == ["completed", "failed", "completed"]
    assert [s.session_id for s in result.steps] == [301, None, 302]
    assert result.total_token_cost == 10 + 20


def test_merge_artifacts_same_type_new_overrides_base() -> None:
    """用例9: _merge_artifacts 同 artifact_type 时 new 覆盖 base。"""
    base_intent = UserIntentArtifact(natural_language_request="旧请求")
    new_intent = UserIntentArtifact(natural_language_request="新请求")

    merged = AgentOrchestrator._merge_artifacts([base_intent], [new_intent])

    assert len(merged) == 1
    assert merged[0].artifact_type == "user_intent"
    # 同类型 new 覆盖 base
    assert merged[0].natural_language_request == "新请求"  # type: ignore[attr-defined]


def test_merge_artifacts_different_types_coexist() -> None:
    """用例10: _merge_artifacts 不同 artifact_type 共存。"""
    intent = UserIntentArtifact(natural_language_request="请求")
    context = ProjectContextArtifact(project_id=1, name="app")

    merged = AgentOrchestrator._merge_artifacts([intent], [context])

    assert len(merged) == 2
    types = {a.artifact_type for a in merged}
    assert types == {"user_intent", "project_context"}


async def test_execute_pipeline_passes_accumulated_artifacts_to_subsequent_agents(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例11: 后续 Agent 接收前序累积的 artifacts（初始 + 已合并）。

    注：_extract_output_artifacts 当前实现返回空列表（final_answer 解析暂不重建
    artifact 对象），所以后续 Agent 的 initial_artifacts 仅包含初始 artifacts。
    此用例验证「累积传递」机制本身：每个 Agent 都至少收到 initial_artifacts。
    """
    runtime.enqueue_session(session_id=1, token_cost=10)
    runtime.enqueue_session(session_id=2, token_cost=20)

    await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution"],
        project_id=1,
        initial_artifacts=initial_artifacts,
    )

    # 第一个 Agent 收到 initial_artifacts
    first_call = runtime.calls[0]
    assert len(first_call["initial_artifacts"]) == 2
    assert {a.artifact_type for a in first_call["initial_artifacts"]} == {
        "user_intent",
        "project_context",
    }
    # 第二个 Agent 也收到 initial_artifacts（累积集 = 初始 + 第一个输出空）
    second_call = runtime.calls[1]
    assert len(second_call["initial_artifacts"]) == 2


async def test_execute_pipeline_passes_execution_callback_to_all_agents(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例12: execution_callback 透传到每个 Agent。"""

    async def _callback(*args: Any, **kwargs: Any) -> None:
        return None

    runtime.enqueue_session(session_id=1, token_cost=10)
    runtime.enqueue_session(session_id=2, token_cost=20)

    await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        execution_callback=_callback,
    )

    assert all(call["execution_callback"] is _callback for call in runtime.calls)


async def test_execute_pipeline_passes_created_by_to_all_agents(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例13: created_by 透传到每个 Agent。"""
    runtime.enqueue_session(session_id=1, token_cost=10)
    runtime.enqueue_session(session_id=2, token_cost=20)
    runtime.enqueue_session(session_id=3, token_cost=30)

    await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=99,
        initial_artifacts=initial_artifacts,
        created_by=777,
    )

    assert all(call["created_by"] == 777 for call in runtime.calls)
    assert all(call["project_id"] == 99 for call in runtime.calls)


async def test_execute_pipeline_generates_uuid_pipeline_id(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例14: pipeline_id 为合法 UUID 字符串。"""
    runtime.enqueue_session(session_id=1, token_cost=10)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation"],
        project_id=1,
        initial_artifacts=initial_artifacts,
    )

    # 验证可解析为 UUID（不抛 ValueError 即合法）
    parsed = uuid.UUID(result.pipeline_id)
    assert str(parsed) == result.pipeline_id


async def test_execute_pipeline_accumulates_token_cost_and_duration(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """用例15: total_token_cost 为各步骤 token_cost 之和，total_duration_seconds 非负。"""
    runtime.enqueue_session(session_id=1, token_cost=100)
    runtime.enqueue_session(session_id=2, token_cost=200)
    runtime.enqueue_session(session_id=3, token_cost=300)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution", "failure_analysis"],
        project_id=1,
        initial_artifacts=initial_artifacts,
    )

    assert result.total_token_cost == 600
    assert result.total_duration_seconds >= 0.0
    # 各步骤 duration_seconds 也应非负
    assert all(s.duration_seconds >= 0.0 for s in result.steps)


def test_extract_output_artifacts_returns_empty_for_empty_final_answer() -> None:
    """用例16: _extract_output_artifacts 处理空 final_answer 返回空列表。"""
    session = _MockSession(session_id=1, final_answer="")
    assert AgentOrchestrator._extract_output_artifacts(session) == []  # type: ignore[arg-type]


def test_extract_output_artifacts_returns_empty_for_invalid_final_answer() -> None:
    """用例17: _extract_output_artifacts 处理非 JSON / 非 dict final_answer 不抛异常。"""
    # 非 JSON 字符串
    session1 = _MockSession(session_id=1, final_answer="not a json")
    assert AgentOrchestrator._extract_output_artifacts(session1) == []  # type: ignore[arg-type]

    # JSON 但非 dict（list）
    session2 = _MockSession(session_id=2, final_answer='[1, 2, 3]')
    assert AgentOrchestrator._extract_output_artifacts(session2) == []  # type: ignore[arg-type]

    # JSON dict 但无 artifacts 字段
    session3 = _MockSession(session_id=3, final_answer='{"foo": "bar"}')
    assert AgentOrchestrator._extract_output_artifacts(session3) == []  # type: ignore[arg-type]

    # JSON dict 但 artifacts 非 list
    session4 = _MockSession(
        session_id=4,
        final_answer='{"artifacts": {"a": 1}}',
    )
    assert AgentOrchestrator._extract_output_artifacts(session4) == []  # type: ignore[arg-type]


async def test_orchestrator_uses_injected_agent_registry(
    runtime: MockRuntime,
    four_agent_registry: AgentRegistry,
    initial_artifacts: List[Artifact],
) -> None:
    """用例18: 自定义 agent_registry 注入生效，禁用后无法执行对应 Agent。"""
    four_agent_registry.disable("test_execution")
    orchestrator = AgentOrchestrator(
        runtime=runtime,  # type: ignore[arg-type]
        agent_registry=four_agent_registry,
    )

    with pytest.raises(AgentError) as exc_info:
        await orchestrator.execute_pipeline(
            pipeline=["test_generation", "test_execution"],
            project_id=1,
            initial_artifacts=initial_artifacts,
        )
    assert exc_info.value.agent_type == "test_execution"


async def test_execute_pipeline_final_artifacts_set_to_accumulated(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """补充用例: result.final_artifacts 为累积 artifacts（初始 + 各 Agent 输出空）。"""
    runtime.enqueue_session(session_id=1, token_cost=10)
    runtime.enqueue_session(session_id=2, token_cost=20)

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation", "test_execution"],
        project_id=1,
        initial_artifacts=initial_artifacts,
    )

    assert result.status == PipelineStatus.COMPLETED
    # final_artifacts 至少包含初始 artifacts（因 _extract_output_artifacts 返回空）
    final_types = {a.artifact_type for a in result.final_artifacts}
    assert "user_intent" in final_types
    assert "project_context" in final_types


async def test_execute_pipeline_does_not_call_runtime_when_validation_fails(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """补充用例: pipeline 校验失败时 runtime.run 不被调用。"""
    with pytest.raises(AgentError):
        await orchestrator.execute_pipeline(
            pipeline=["unknown_agent"],
            project_id=1,
            initial_artifacts=initial_artifacts,
        )
    assert len(runtime.calls) == 0


async def test_execute_pipeline_step_error_message_recorded(
    orchestrator: AgentOrchestrator,
    runtime: MockRuntime,
    initial_artifacts: List[Artifact],
) -> None:
    """补充用例: 失败步骤的 error 字段记录异常字符串。"""
    runtime.enqueue_failure(ValueError("specific error message"))

    result = await orchestrator.execute_pipeline(
        pipeline=["test_generation"],
        project_id=1,
        initial_artifacts=initial_artifacts,
        stop_on_failure=True,
    )

    assert result.steps[0].error == "specific error message"
