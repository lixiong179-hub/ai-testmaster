"""TestGenerationAgent - 测试用例生成示范 Agent。

设计目的：
    作为 Agent 框架的首个业务 Agent，验证 AgentDefinition + AgentRuntime +
    工具注册的端到端链路。Agent 自身保持「瘦壳」：仅提供 system_prompt 与
    工具清单，执行委托 AgentRuntime，避免在 Agent 类内构造 Runtime 造成
    依赖膨胀与测试困难（Runtime 由调用方注入）。

执行入口：
    agent = TestGenerationAgent()
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
    # 仅类型注解使用，运行时不导入避免与 agent.__init__ 形成导入环
    from app.services.agent.runtime import AgentRuntime


# TestGenerationAgent 专属 system_prompt（中文，聚焦用例生成场景）
_SYSTEM_PROMPT = """你是 AI TestMaster 的测试用例生成专家，负责根据用户意图与项目上下文产出结构化、可执行的测试用例。

【输入 artifacts】
- user_intent: 用户此次的测试目标与关注点
- project_context: 被测项目的技术栈、模块结构与命名约定
- failure_history: 历史失败记录，用于规避已知缺陷与补充回归场景

【工具使用流程】
1. 先调用 get_project_info 了解项目模块与约定；
2. 再调用 query_similar_test_cases 检索相似用例，避免重复生成；
3. 接着调用 query_failure_history 查阅失败历史，针对性补充边界与异常场景；
4. 然后调用 create_test_case 写入用例，steps 中每个步骤须含 action（click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress），target/value/expected 可选；
5. 最后调用 validate_test_case_syntax 校验步骤完整性，若有 warnings 则修正后重新创建。

【输出约定】
全部用例创建并校验通过后，必须调用 final_answer 工具终止会话，参数包含 test_case_id 与 summary（本次生成用例的摘要）。禁止在未调用 final_answer 前结束。"""


class TestGenerationAgent(AgentBase):
    """测试用例生成 Agent。

    通过 definition() 暴露配置（system_prompt + 工具清单 + 能力声明），
    通过 run() 接受执行入口并委托 AgentRuntime 驱动多轮 function calling。
    """

    @classmethod
    def definition(cls) -> AgentDefinition:
        """返回 TestGenerationAgent 配置定义。

        max_iterations / token_budget 留 None，由 settings 默认值接管，
        避免在定义层硬编码运行时参数。
        """
        return AgentDefinition(
            agent_type="test_generation",
            system_prompt=_SYSTEM_PROMPT,
            tools=[
                "get_project_info",
                "query_similar_test_cases",
                "query_failure_history",
                "create_test_case",
                "validate_test_case_syntax",
                "final_answer",
            ],
            default_capabilities=[
                "test_case:create",
                "test_case:validate",
            ],
            max_iterations=None,
            token_budget=None,
            description="根据 user_intent + project_context + failure_history 生成结构化测试用例",
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
        """执行测试用例生成会话，委托 AgentRuntime 驱动。

        Args:
            artifacts: 初始上下文 artifacts（user_intent / project_context /
                failure_history）。
            execution_callback: 客户端工具执行回调，None 表示无客户端工具场景。
            db: 预留参数；runtime 自带 db 时不会使用，供未来内联执行扩展。
            project_id: 项目 ID，透传给 runtime.run。
            created_by: 触发会话的用户 ID。
            runtime: AgentRuntime 实例，必须由调用方注入。

        Returns:
            AgentSession: 会话最终状态记录。

        Raises:
            NotImplementedError: 未提供 runtime 参数时抛出，避免在 Agent 类内
                构造 Runtime 造成依赖膨胀。
        """
        # db 当前由 runtime 自带，此处不直接使用，保留参数以对齐调用契约
        _ = db
        if runtime is None:
            raise NotImplementedError("TestGenerationAgent.run 需要 runtime 参数")
        return await runtime.run(
            agent_type="test_generation",
            project_id=project_id,
            initial_artifacts=artifacts,
            execution_callback=execution_callback,
            created_by=created_by,
        )


__all__ = ["TestGenerationAgent"]
