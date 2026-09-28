"""Agent 默认注册入口。

集中注册各业务 Agent 的 AgentDefinition 到全局 AgentRegistry，新增 Agent
在此追加一行 register 调用即可被 AgentRuntime 路由。模块级自动调用一次，
try/except 容忍重复导入与注册异常，避免阻断包加载。

当前注册的 5 个 Agent 构成完整测试管线：
    1. test_generation     - 测试用例生成
    2. test_execution      - 测试执行
    3. failure_analysis    - 失败分析
    4. locator_healing     - 定位器修复
    5. visual_validation   - 视觉校验（Phase 2）
"""
from __future__ import annotations

from loguru import logger

from app.services.agent.agents.failure_analysis_agent import FailureAnalysisAgent
from app.services.agent.agents.locator_healing_agent import LocatorHealingAgent
from app.services.agent.agents.test_execution_agent import TestExecutionAgent
from app.services.agent.agents.test_generation_agent import TestGenerationAgent
from app.services.agent.agents.visual_validation_agent import VisualValidationAgent
from app.services.agent.registry import get_global_registry


def register_default_agents() -> None:
    """注册内置 Agent 定义到全局 AgentRegistry。

    AgentRegistry.register 对同一 agent_type 覆盖旧定义，因此重复调用幂等。
    """
    registry = get_global_registry()
    registry.register(TestGenerationAgent.definition())
    registry.register(TestExecutionAgent.definition())
    registry.register(FailureAnalysisAgent.definition())
    registry.register(LocatorHealingAgent.definition())
    registry.register(VisualValidationAgent.definition())


# 模块级自动注册：导入即生效，try/except 防止重复注册异常阻断包加载
try:
    register_default_agents()
except Exception as e:  # noqa: BLE001 - 注册失败不应阻断包加载
    logger.warning(f"register_default_agents 跳过: {e}")


__all__ = ["register_default_agents"]
