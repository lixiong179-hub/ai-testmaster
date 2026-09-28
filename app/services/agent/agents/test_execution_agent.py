"""TestExecutionAgent - 测试执行 Agent。

设计目的：
    作为 4 Agent 串联管线的第二环，接收 TestGenerationAgent 产出的测试用例，
    驱动浏览器执行步骤，收集执行结果与失败证据。

执行入口：
    agent = TestExecutionAgent()
    session = await agent.run(
        artifacts, callback, runtime=runtime, project_id=1, created_by=user_id,
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from app.models.agent_session import AgentSession
from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentBase, AgentDefinition

if TYPE_CHECKING:
    from app.services.agent.runtime import AgentRuntime


_SYSTEM_PROMPT = """你是 AI TestMaster 的测试执行专家，负责驱动浏览器执行测试用例并收集结果。

【输入 artifacts】
- test_case: 待执行的测试用例（含步骤列表）
- project_context: 被测项目的技术栈与 URL
- execution_state: 前序步骤的执行状态（如已登录、已导航）

【工具使用流程】
1. 调用 get_test_case 获取待执行用例的完整步骤；
2. 按步骤顺序调用 click_element / input_element / wait / scroll 执行操作；
3. 每步执行后调用 screenshot 截图作为证据；
4. 遇到断言失败时记录失败信息，继续执行后续步骤（除非步骤依赖前置结果）；
5. 全部步骤执行完毕后调用 final_answer 终止会话，参数包含 execution_summary
  （成功/失败步骤数）与 failed_steps（失败步骤索引与原因列表）。

【输出约定】
final_answer 必须包含 execution_summary 与 failed_steps 字段。"""


class TestExecutionAgent(AgentBase):
    """测试执行 Agent。

    接收测试用例 artifacts，驱动浏览器执行步骤，输出执行结果摘要。
    """

    @classmethod
    def definition(cls) -> AgentDefinition:
        """返回 TestExecutionAgent 配置定义。"""
        return AgentDefinition(
            agent_type="test_execution",
            system_prompt=_SYSTEM_PROMPT,
            tools=[
                "get_test_case",
                "click_element",
                "input_element",
                "wait",
                "scroll",
                "screenshot",
                "final_answer",
            ],
            default_capabilities=[
                "test_case:execute",
                "browser:control",
            ],
            max_iterations=None,
            token_budget=None,
            description="驱动浏览器执行测试用例步骤，收集执行结果与失败证据",
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
        """执行测试用例，委托 AgentRuntime 驱动多轮 function calling。

        Args:
            artifacts: 初始上下文（test_case / project_context / execution_state）。
            execution_callback: 客户端工具执行回调，由测试执行引擎提供。
            db: 预留参数；runtime 自带 db 时不会使用。
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
            raise NotImplementedError("TestExecutionAgent.run 需要 runtime 参数")
        return await runtime.run(
            agent_type="test_execution",
            project_id=project_id,
            initial_artifacts=artifacts,
            execution_callback=execution_callback,
            created_by=created_by,
        )


__all__ = ["TestExecutionAgent"]
