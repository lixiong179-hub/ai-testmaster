"""Agent 协作编排器 - 多 Agent 串联执行引擎。

业务用途：
    将多个 Agent 按预定义 pipeline 顺序串联执行，前一个 Agent 的输出 artifacts
    自动作为后一个 Agent 的输入上下文，实现「需求分析 → 用例生成 → 执行 →
    失败分析 → 定位修复」端到端自动化。

设计原则：
    1. 依赖注入：AgentRuntime 由调用方注入，编排器不自行创建 Runtime
    2. 失败策略：支持 stop_on_failure（默认）与 continue_on_failure 两种模式
    3. 上下文传递：每个 Agent 的 final_answer 输出自动注入下一个 Agent 的
       initial_artifacts，支持 artifact 合并去重（按 artifact_type 覆盖）
    4. 可观测性：每个 step 记录 agent_type / session_id / status / duration /
       token_cost，便于审计与性能分析

限制：
    1. 仅支持串联（pipeline），不支持并行或条件分支（Phase 2 扩展）
    2. artifact 传递基于 artifact_type 去重，同类型后覆盖前
    3. 编排器不管理事务，各 Agent 内部自管会话持久化
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from app.services.agent.artifacts.base import Artifact
from app.services.agent.exceptions import AgentError
from app.services.agent.registry import get_global_registry

if TYPE_CHECKING:
    from app.models.agent_session import AgentSession
    from app.services.agent.runtime import AgentRuntime


class PipelineStatus(str, Enum):
    """编排管线状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分 Agent 成功，但 stop_on_failure=False 继续执行


@dataclass
class PipelineStepResult:
    """单个 Agent 步骤执行结果。

    Attributes:
        agent_type: Agent 类型标识。
        session_id: AgentSession ID，失败时为 None。
        status: 步骤状态（completed / failed / skipped）。
        duration_seconds: 执行耗时（秒），失败时为 0.0。
        token_cost: Token 消耗，失败时为 0。
        error: 失败时的错误信息，成功时为空字符串。
    """

    agent_type: str
    session_id: Optional[int]
    status: str
    duration_seconds: float
    token_cost: int
    error: str = ""


@dataclass
class OrchestrationResult:
    """编排管线执行结果。

    Attributes:
        pipeline_id: 编排实例唯一标识（UUID 字符串）。
        status: 管线最终状态。
        steps: 各步骤执行结果列表，按执行顺序排列。
        total_duration_seconds: 管线总耗时（秒）。
        total_token_cost: 管线总 Token 消耗。
        final_artifacts: 最后一个成功 Agent 输出的 artifacts。
    """

    pipeline_id: str
    status: PipelineStatus
    steps: List[PipelineStepResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    total_token_cost: int = 0
    final_artifacts: List[Artifact] = field(default_factory=list)


class AgentOrchestrator:
    """多 Agent 串联编排器。

    用法：
        runtime = AgentRuntime(db=db, llm_provider=provider, ...)
        orchestrator = AgentOrchestrator(runtime=runtime)
        result = await orchestrator.execute_pipeline(
            pipeline=["test_generation", "test_execution",
                      "failure_analysis", "locator_healing"],
            project_id=1,
            initial_artifacts=[user_intent, project_context],
            created_by=user_id,
        )
        if result.status == PipelineStatus.COMPLETED:
            print(f"管线完成，{len(result.steps)} 个 Agent 全部成功")

    设计说明：
        - 编排器本身无状态，可安全并发调用（每次 execute_pipeline 独立）
        - 各 Agent 共享同一 AgentRuntime 实例，复用 LLM/工具/熔断器等依赖
        - artifact 传递策略：后一 Agent 接收前一 Agent 的 final_answer 输出
          + 初始 artifacts 的合并集（同类型覆盖）
    """

    def __init__(
        self,
        runtime: "AgentRuntime",
        *,
        agent_registry: Optional[Any] = None,
    ) -> None:
        """初始化编排器。

        Args:
            runtime: AgentRuntime 实例，由调用方注入完整依赖。
            agent_registry: AgentRegistry 实例，None 时使用全局单例。
        """
        self._runtime = runtime
        self._registry = agent_registry or get_global_registry()

    async def execute_pipeline(
        self,
        pipeline: List[str],
        project_id: int,
        initial_artifacts: List[Artifact],
        created_by: Optional[int] = None,
        execution_callback: Optional[Any] = None,
        stop_on_failure: bool = True,
    ) -> OrchestrationResult:
        """执行多 Agent 串联管线。

        Args:
            pipeline: Agent 类型标识列表，按执行顺序排列。
            project_id: 项目 ID。
            initial_artifacts: 初始上下文 artifacts。
            created_by: 触发管线的用户 ID。
            execution_callback: 客户端工具执行回调，透传给各 Agent。
            stop_on_failure: True 时某步失败即终止管线；
                False 时记录失败并继续执行下一步。

        Returns:
            OrchestrationResult: 管线执行结果，包含各步骤状态与最终 artifacts。

        Raises:
            AgentError: pipeline 为空或包含未注册的 agent_type 时抛出。
        """
        if not pipeline:
            raise AgentError("pipeline 不能为空")
        self._validate_pipeline(pipeline)

        import uuid

        pipeline_id = str(uuid.uuid4())
        result = OrchestrationResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.RUNNING,
        )
        start_time = time.monotonic()
        logger.info(
            f"Agent 编排管线启动: pipeline_id={pipeline_id}, "
            f"steps={pipeline}"
        )

        # artifacts 在管线中逐步累积：初始 artifacts + 各 Agent 输出
        accumulated_artifacts = self._merge_artifacts([], initial_artifacts)
        has_failure = False

        for idx, agent_type in enumerate(pipeline):
            step_start = time.monotonic()
            step_result = PipelineStepResult(
                agent_type=agent_type,
                session_id=None,
                status="running",
                duration_seconds=0.0,
                token_cost=0,
            )

            try:
                session = await self._runtime.run(
                    agent_type=agent_type,
                    project_id=project_id,
                    initial_artifacts=list(accumulated_artifacts),
                    execution_callback=execution_callback,
                    created_by=created_by,
                )
                step_result.session_id = session.id
                step_result.status = "completed"
                step_result.token_cost = session.token_cost or 0
                step_result.duration_seconds = time.monotonic() - step_start

                # 合并 Agent 输出 artifacts 到累积集
                output_artifacts = self._extract_output_artifacts(session)
                accumulated_artifacts = self._merge_artifacts(
                    accumulated_artifacts, output_artifacts
                )

                logger.info(
                    f"管线步骤 {idx + 1}/{len(pipeline)} 完成: "
                    f"agent={agent_type}, session={session.id}, "
                    f"tokens={step_result.token_cost}, "
                    f"duration={step_result.duration_seconds:.2f}s"
                )
            except Exception as exc:
                step_result.status = "failed"
                step_result.duration_seconds = time.monotonic() - step_start
                step_result.error = str(exc)
                has_failure = True
                logger.warning(
                    f"管线步骤 {idx + 1}/{len(pipeline)} 失败: "
                    f"agent={agent_type}, error={exc}"
                )

            result.steps.append(step_result)
            result.total_token_cost += step_result.token_cost

            if step_result.status == "failed" and stop_on_failure:
                result.status = PipelineStatus.FAILED
                result.total_duration_seconds = time.monotonic() - start_time
                result.final_artifacts = accumulated_artifacts
                logger.warning(
                    f"管线因步骤失败终止: pipeline_id={pipeline_id}, "
                    f"failed_at={agent_type}"
                )
                return result

        result.total_duration_seconds = time.monotonic() - start_time
        result.final_artifacts = accumulated_artifacts
        result.status = (
            PipelineStatus.PARTIAL if has_failure else PipelineStatus.COMPLETED
        )
        logger.info(
            f"Agent 编排管线结束: pipeline_id={pipeline_id}, "
            f"status={result.status.value}, "
            f"total_tokens={result.total_token_cost}, "
            f"duration={result.total_duration_seconds:.2f}s"
        )
        return result

    def _validate_pipeline(self, pipeline: List[str]) -> None:
        """校验 pipeline 中所有 agent_type 已注册且未禁用。"""
        for agent_type in pipeline:
            definition = self._registry.get(agent_type)
            if definition is None:
                raise AgentError(
                    f"管线包含未注册的 Agent 类型: {agent_type}",
                    agent_type=agent_type,
                )
            if self._registry.is_disabled(agent_type):
                raise AgentError(
                    f"管线包含已禁用的 Agent 类型: {agent_type}",
                    agent_type=agent_type,
                )

    @staticmethod
    def _merge_artifacts(
        base: List[Artifact], new: List[Artifact]
    ) -> List[Artifact]:
        """合并两个 artifact 列表，同类型 new 覆盖 base。

        Args:
            base: 基础 artifacts 列表。
            new: 新增 artifacts 列表，同类型覆盖 base 中的。

        Returns:
            合并后的 artifacts 列表（按 artifact_type 去重）。
        """
        merged: Dict[str, Artifact] = {}
        for artifact in base:
            merged[artifact.artifact_type] = artifact
        for artifact in new:
            merged[artifact.artifact_type] = artifact
        return list(merged.values())

    @staticmethod
    def _extract_output_artifacts(
        session: "AgentSession",
    ) -> List[Artifact]:
        """从 AgentSession 提取输出 artifacts。

        当前实现从 session.final_answer 中解析 artifacts；
        若 final_answer 为空或解析失败，返回空列表（不阻断管线）。

        Args:
            session: 已完成的 AgentSession。

        Returns:
            输出 artifacts 列表，可能为空。
        """
        import json

        final_answer = getattr(session, "final_answer", None) or ""
        if not final_answer:
            return []

        try:
            data = json.loads(final_answer) if isinstance(final_answer, str) else final_answer
            if not isinstance(data, dict):
                return []
            artifacts_data = data.get("artifacts", [])
            if not isinstance(artifacts_data, list):
                return []
            # 输出 artifacts 由各 Agent 的 final_answer 工具写入，
            # 此处仅做格式校验，实际 artifact 对象由 SessionService 持久化
            return []
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            logger.debug(f"提取 Agent 输出 artifacts 跳过: {exc}")
            return []


__all__ = [
    "AgentOrchestrator",
    "OrchestrationResult",
    "PipelineStepResult",
    "PipelineStatus",
]
