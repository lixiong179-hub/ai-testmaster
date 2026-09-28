"""Agent 定义与抽象基类。

设计目的：
    AgentDefinition 是描述 Agent 配置的纯数据载体（system_prompt / 工具列表 /
    能力声明 / 迭代上限 / Token 预算），由 AgentRegistry 注册并由 AgentRuntime
    驱动执行。AgentBase 是具体 Agent 的抽象基类，子类（如 TestGenerationAgent）
    通过 definition() 类方法暴露配置，通过 run() 方法接受执行入口（通常委托
    给 AgentRuntime，也可覆盖实现定制循环）。

设计原则：
    - 配置与执行分离：AgentDefinition 只描述「能做什么」，AgentRuntime 决定「怎么做」
    - 注册即生效：AgentRegistry.register(definition) 后即可被 AgentRuntime.run(agent_type) 调用
    - 子类最少实现：通常只需实现 definition() 类方法，run() 默认委托 AgentRuntime
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    # 仅类型注解使用，运行时不导入避免循环依赖
    from app.models.agent_session import AgentSession
    from app.services.agent.artifacts.base import Artifact
    from app.services.agent.tools.base_tool import ToolResult


@dataclass(frozen=True)
class AgentDefinition:
    """Agent 配置定义。

    Attributes:
        agent_type: Agent 类型标识，与 AgentSession.agent_type 对齐
            （test_generation/failure_analysis/visual_validation/locator_healing）。
        system_prompt: 系统提示词，定义 Agent 的角色、目标、约束。
        tools: 工具名列表，对应 ToolRegistry 中注册的工具 name。
        default_capabilities: 默认能力声明，用于权限校验与 UI 展示
            （如 "test_case:create" / "test_case:validate"）。
        max_iterations: 单会话最大迭代次数；None 表示用 settings.AI_AGENT_MAX_ITERATIONS。
        token_budget: 单会话 Token 预算上限；None 表示用 settings.AI_AGENT_DAILY_TOKEN_BUDGET。
        description: 人类可读的 Agent 描述，用于 OpenAPI 文档与日志。
    """

    agent_type: str
    system_prompt: str
    tools: List[str] = field(default_factory=list)
    default_capabilities: List[str] = field(default_factory=list)
    max_iterations: Optional[int] = None
    token_budget: Optional[int] = None
    description: str = ""


class AgentBase(ABC):
    """Agent 抽象基类。

    子类（如 TestGenerationAgent）必须实现：
        - definition() 类方法：返回 AgentDefinition，注册到 AgentRegistry
        - run() 实例方法：执行入口，通常委托给 AgentRuntime，也可覆盖实现定制循环

    使用方式：
        class TestGenerationAgent(AgentBase):
            @classmethod
            def definition(cls) -> AgentDefinition:
                return AgentDefinition(
                    agent_type="test_generation",
                    system_prompt="...",
                    tools=["get_project_info", "create_test_case"],
                )

            async def run(self, artifacts, execution_callback=None):
                runtime = self._build_runtime()
                return await runtime.run(
                    agent_type="test_generation",
                    project_id=...,
                    initial_artifacts=artifacts,
                    execution_callback=execution_callback,
                )
    """

    @classmethod
    @abstractmethod
    def definition(cls) -> AgentDefinition:
        """返回 Agent 配置定义。

        子类必须实现，返回包含 agent_type / system_prompt / tools 等字段的
        AgentDefinition 实例，供 AgentRegistry.register() 使用。
        """

    @abstractmethod
    async def run(
        self,
        artifacts: List["Artifact"],
        execution_callback: Optional[Any] = None,
    ) -> "AgentSession":
        """Agent 执行入口。

        Args:
            artifacts: 初始上下文 artifacts 列表（user_intent / project_context 等）。
            execution_callback: 客户端工具执行回调，由测试执行引擎提供；
                None 表示无客户端工具调用场景。

        Returns:
            AgentSession: 会话最终状态记录，包含 status / token_cost / iteration_count。

        Raises:
            AgentLoopDetected: 循环检测触发。
            TokenBudgetExceeded: Token 预算超限。
            MaxIterationsExceeded: 迭代次数触达上限。
            ToolExecutionError: 工具执行失败。
            CircuitBreakerOpen: 熔断器开启。
        """


__all__ = ["AgentDefinition", "AgentBase"]
