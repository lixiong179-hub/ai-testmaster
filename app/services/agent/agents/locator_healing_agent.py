"""LocatorHealingAgent - 定位器修复 Agent。

设计目的：
    作为 4 Agent 串联管线的第四环，接收 FailureAnalysisAgent 产出的失败分类，
    针对 dom_changed / element_gone 类型失败，生成新的 CSS 选择器并验证可用性。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from app.models.agent_session import AgentSession
from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentBase, AgentDefinition

if TYPE_CHECKING:
    from app.services.agent.runtime import AgentRuntime


_SYSTEM_PROMPT = """你是 AI TestMaster 的定位器修复专家，负责为失败的测试步骤生成新的 CSS 选择器。

【输入 artifacts】
- execution_state: 执行结果摘要，含失败步骤列表
- failure_history: 历史失败与修复记录
- test_case: 关联的测试用例

【修复策略】
1. dom_changed: 元素存在但选择器失效 → 基于当前 DOM 生成新选择器
2. element_gone: 元素消失 → 搜索功能等价的替代元素
3. load_delay: 不修复，建议重试
4. env_noise: 不修复，建议跳过

【工具使用流程】
1. 调用 query_locator_history 获取失败步骤的历史选择器变更；
2. 调用 get_dom 获取当前页面 DOM 快照；
3. 分析 DOM 结构，生成候选选择器（优先语义化：text > role > class > xpath）；
4. 调用 click_element 验证候选选择器是否可交互（仅验证不产生副作用）；
5. 调用 final_answer 终止，参数包含 healing_results
  （每条修复含 step_index / old_selector / new_selector / confidence）。

【输出约定】
final_answer 必须包含 healing_results 字段，每条修复含：
- step_index: 失败步骤索引
- old_selector: 原选择器
- new_selector: 新选择器
- confidence: 0.0-1.0 置信度（<0.7 标记 low_confidence）
- strategy: dom_changed / element_gone"""


class LocatorHealingAgent(AgentBase):
    """定位器修复 Agent。

    接收失败分析结果，针对可修复类型生成新选择器并验证。
    """

    @classmethod
    def definition(cls) -> AgentDefinition:
        """返回 LocatorHealingAgent 配置定义。"""
        return AgentDefinition(
            agent_type="locator_healing",
            system_prompt=_SYSTEM_PROMPT,
            tools=[
                "get_test_case",
                "query_locator_history",
                "get_dom",
                "click_element",
                "final_answer",
            ],
            default_capabilities=[
                "locator:heal",
                "dom:read",
            ],
            max_iterations=None,
            token_budget=None,
            description="为失败步骤生成新 CSS 选择器并验证可用性，实现自愈",
        )

    async def run(
        self,
        artifacts: List[Artifact],
        execution_callback: Optional[Any] = None,
        *,
        db: Optional[Any] = None,
        project_id: Optional[int] = None,
        created_by: Optional[int] = None,
        runtime: Optional["AgentRuntime"] = None,
    ) -> AgentSession:
        """执行定位器修复，委托 AgentRuntime 驱动多轮 function calling。

        Args:
            artifacts: 初始上下文（execution_state / failure_history / test_case）。
            execution_callback: 客户端工具执行回调，用于 get_dom / click_element。
            db: 预留参数。
            project_id: 项目 ID。
            created_by: 触发会话的用户 ID。
            runtime: AgentRuntime 实例，必须由调用方注入。

        Returns:
            AgentSession: 会话最终状态记录。

        Raises:
            NotImplementedError: 未提供 runtime 参数时抛出。
        """
        _ = db
        if runtime is None:
            raise NotImplementedError("LocatorHealingAgent.run 需要 runtime 参数")
        return await runtime.run(
            agent_type="locator_healing",
            project_id=project_id,
            initial_artifacts=artifacts,
            execution_callback=execution_callback,
            created_by=created_by,
        )


__all__ = ["LocatorHealingAgent"]
