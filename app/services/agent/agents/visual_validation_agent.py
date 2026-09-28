"""VisualValidationAgent - 视觉校验 Agent（Task 11）。

作为 5 Agent 串联管线的第五环（可选），负责在测试执行后对关键页面截图
进行视觉回归校验。对比当前截图与基线，生成 Diff 记录，必要时触发 LLM
语义分析判断差异是否为真实缺陷。

Agent 类型：visual_validation
工具集：
    - get_baseline        : 查询页面活跃基线
    - compare_visual      : 执行视觉对比
    - update_baseline     : 更新基线截图
    - final_answer        : 提交视觉校验结论
"""
from __future__ import annotations

from typing import Any, List, Optional

from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentBase, AgentDefinition
from app.services.agent.runtime import AgentRuntime
from app.services.agent.session_service import AgentSession

_SYSTEM_PROMPT = """你是视觉回归测试专家。你的职责是对比当前页面截图与基线截图，
判断是否存在视觉回归缺陷。

工作流程：
1. 调用 get_baseline 获取页面的活跃基线信息
2. 调用 compare_visual 对比当前截图与基线
3. 根据对比结果判断差异类别：
   - 差异百分比 < 0.1%：视觉噪声，标记为通过
   - 差异百分比 0.1%-5%：轻微差异，需人工确认
   - 差异百分比 > 5%：显著差异，可能为真实缺陷
4. 若差异显著，建议是否更新基线（UI 预期变更）或标记为缺陷
5. 调用 final_answer 提交视觉校验结论

判断原则：
- 优先关注布局错位、元素丢失、文字截断等结构性缺陷
- 忽略动态内容（广告、时间戳、轮播图）导致的差异
- 对主题切换/品牌色变更场景建议使用 ignore_colors Match Level
"""


class VisualValidationAgent(AgentBase):
    """视觉校验 Agent。

    在测试执行后对关键页面截图进行视觉回归校验，对比当前截图与基线，
    生成 Diff 记录并判断差异类别。
    """

    @classmethod
    def definition(cls) -> AgentDefinition:
        """返回 Agent 配置定义。"""
        return AgentDefinition(
            agent_type="visual_validation",
            system_prompt=_SYSTEM_PROMPT,
            tools=[
                "get_baseline",
                "compare_visual",
                "update_baseline",
                "final_answer",
            ],
            default_capabilities=[
                "visual:compare",
                "baseline:read",
                "baseline:update",
            ],
            description="对比当前截图与基线，执行视觉回归校验并判断差异类别",
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
        """执行视觉校验 Agent。

        委托 AgentRuntime 执行，由 Runtime 负责工具调用循环与 LLM 交互。
        """
        if runtime is None:
            raise NotImplementedError("VisualValidationAgent.run 需要 runtime 参数")
        return await runtime.run(
            agent_type="visual_validation",
            project_id=project_id,
            initial_artifacts=artifacts,
            execution_callback=execution_callback,
            created_by=created_by,
        )


__all__ = ["VisualValidationAgent"]
