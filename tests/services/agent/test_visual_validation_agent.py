"""VisualValidationAgent 单元测试。

覆盖：
    - definition() 返回正确的 agent_type
    - definition() 包含必需工具
    - definition() 包含必需 capabilities
    - run() 委托 AgentRuntime 执行
    - run() 无 runtime 时抛 NotImplementedError
"""
from __future__ import annotations

from typing import Any, List, Optional
from unittest.mock import AsyncMock

import pytest

from app.services.agent.agents.visual_validation_agent import VisualValidationAgent
from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentDefinition


class _MockSession:
    """模拟 AgentSession。"""

    def __init__(self, session_id: int = 1) -> None:
        self.id = session_id
        self.token_cost = 100
        self.final_answer = ""
        self.status = "completed"


class TestVisualValidationAgentDefinition:
    """VisualValidationAgent definition 测试。"""

    def test_agent_type_is_visual_validation(self) -> None:
        """agent_type 为 visual_validation。"""
        defn = VisualValidationAgent.definition()
        assert defn.agent_type == "visual_validation"

    def test_definition_returns_agent_definition(self) -> None:
        """definition() 返回 AgentDefinition 实例。"""
        defn = VisualValidationAgent.definition()
        assert isinstance(defn, AgentDefinition)

    def test_definition_has_required_tools(self) -> None:
        """包含必需工具：get_baseline / compare_visual / update_baseline / final_answer。"""
        defn = VisualValidationAgent.definition()
        assert "get_baseline" in defn.tools
        assert "compare_visual" in defn.tools
        assert "update_baseline" in defn.tools
        assert "final_answer" in defn.tools

    def test_definition_has_capabilities(self) -> None:
        """包含视觉校验相关 capabilities。"""
        defn = VisualValidationAgent.definition()
        assert "visual:compare" in defn.default_capabilities
        assert "baseline:read" in defn.default_capabilities
        assert "baseline:update" in defn.default_capabilities

    def test_definition_has_system_prompt(self) -> None:
        """system_prompt 非空。"""
        defn = VisualValidationAgent.definition()
        assert defn.system_prompt
        assert "视觉回归" in defn.system_prompt

    def test_definition_has_description(self) -> None:
        """description 非空。"""
        defn = VisualValidationAgent.definition()
        assert defn.description
        assert "视觉" in defn.description


class TestVisualValidationAgentRun:
    """VisualValidationAgent run 方法测试。"""

    async def test_run_delegates_to_runtime(self) -> None:
        """run() 委托 AgentRuntime.run() 执行。"""
        mock_runtime = AsyncMock()
        mock_runtime.run.return_value = _MockSession(session_id=42)

        agent = VisualValidationAgent()
        result = await agent.run(
            artifacts=[],
            runtime=mock_runtime,
            project_id=1,
            created_by=10,
        )

        assert result.id == 42
        mock_runtime.run.assert_called_once()
        call_kwargs = mock_runtime.run.call_args
        assert call_kwargs.kwargs["agent_type"] == "visual_validation"
        assert call_kwargs.kwargs["project_id"] == 1
        assert call_kwargs.kwargs["created_by"] == 10

    async def test_run_without_runtime_raises(self) -> None:
        """无 runtime 参数时抛 NotImplementedError。"""
        agent = VisualValidationAgent()
        with pytest.raises(NotImplementedError, match="需要 runtime 参数"):
            await agent.run(artifacts=[], runtime=None)

    async def test_run_passes_artifacts_to_runtime(self) -> None:
        """run() 将 artifacts 透传给 runtime。"""
        mock_runtime = AsyncMock()
        mock_runtime.run.return_value = _MockSession()

        class _StubArtifact(Artifact):
            artifact_type: str = "test_stub"
            description: str = "测试桩"

        artifacts: List[Artifact] = [_StubArtifact()]
        agent = VisualValidationAgent()
        await agent.run(artifacts=artifacts, runtime=mock_runtime)

        call_kwargs = mock_runtime.run.call_args.kwargs
        assert call_kwargs["initial_artifacts"] == artifacts

    async def test_run_passes_execution_callback(self) -> None:
        """run() 透传 execution_callback。"""
        mock_runtime = AsyncMock()
        mock_runtime.run.return_value = _MockSession()

        async def _callback(*args: Any, **kwargs: Any) -> None:
            return None

        agent = VisualValidationAgent()
        await agent.run(
            artifacts=[],
            runtime=mock_runtime,
            execution_callback=_callback,
        )

        call_kwargs = mock_runtime.run.call_args.kwargs
        assert call_kwargs["execution_callback"] is _callback
