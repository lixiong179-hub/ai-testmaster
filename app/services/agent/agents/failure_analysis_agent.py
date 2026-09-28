"""FailureAnalysisAgent - 失败分析 Agent。

设计目的：
    作为 4 Agent 串联管线的第三环，接收 TestExecutionAgent 产出的失败步骤列表，
    分析失败根因并分类（element_gone / dom_changed / load_delay / env_noise），
    为 LocatorHealingAgent 提供决策依据。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from app.models.agent_session import AgentSession
from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentBase, AgentDefinition

if TYPE_CHECKING:
    from app.services.agent.runtime import AgentRuntime


_SYSTEM_PROMPT = """你是 AI TestMaster 的失败分析专家，负责分析测试执行失败步骤的根因并分类。

【输入 artifacts】
- execution_state: 执行结果摘要，含成功/失败步骤数
- failure_history: 历史失败记录，用于识别重复模式
- test_case: 关联的测试用例

【分析维度】
1. element_gone: 元素从 DOM 消失（页面跳转/重构/删除）
2. dom_changed: DOM 结构变更但元素存在（class/id/层级变化）
3. load_delay: 元素未及时加载（异步渲染/网络延迟）
4. env_noise: 环境噪声（弹窗/网络抖动/权限拦截）

【工具使用流程】
1. 调用 query_audit 查询自愈审计记录，识别是否为已知失败模式；
2. 调用 query_locator_history 查询定位器历史变更；
3. 调用 get_test_case 获取失败步骤的详细操作与预期；
4. 综合分析后调用 final_answer 终止，参数包含 failure_classifications
  （每条失败步骤的 failure_type / confidence / suggested_strategy）。

【输出约定】
final_answer 必须包含 failure_classifications 字段，每条分类含：
- step_index: 失败步骤索引
- failure_type: element_gone / dom_changed / load_delay / env_noise
- confidence: 0.0-1.0 置信度
- suggested_strategy: retry / ai_heal / skip"""


class FailureAnalysisAgent(AgentBase):
    """失败分析 Agent。

    接收执行失败结果，分析根因并分类，输出修复策略建议。
    """

    @classmethod
    def definition(cls) -> AgentDefinition:
        """返回 FailureAnalysisAgent 配置定义。"""
        return AgentDefinition(
            agent_type="failure_analysis",
            system_prompt=_SYSTEM_PROMPT,
            tools=[
                "get_test_case",
                "query_audit",
                "query_locator_history",
                "final_answer",
            ],
            default_capabilities=[
                "failure:analyze",
                "audit:read",
            ],
            max_iterations=None,
            token_budget=None,
            description="分析测试执行失败步骤的根因并分类，为定位修复提供决策依据",
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
        """执行失败分析，委托 AgentRuntime 驱动多轮 function calling。

        Args:
            artifacts: 初始上下文（execution_state / failure_history / test_case）。
            execution_callback: 客户端工具执行回调。
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
            raise NotImplementedError("FailureAnalysisAgent.run 需要 runtime 参数")
        return await runtime.run(
            agent_type="failure_analysis",
            project_id=project_id,
            initial_artifacts=artifacts,
            execution_callback=execution_callback,
            created_by=created_by,
        )


__all__ = ["FailureAnalysisAgent"]
