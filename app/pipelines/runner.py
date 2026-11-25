"""
Pipeline Runner 执行引擎

本模块定义 PipelineRunner，负责按依赖顺序执行 Step，
处理缓存命中、重试、降级、暂停等流程。

核心类概览：
    - PipelineRunner : 流水线执行引擎

设计原则：
    - Step 按注册顺序执行，通过 requires/produces 自动拓扑排序
    - 缓存命中时跳过执行，直接复用产物
    - 重试耗尽后调用 fallback 降级
    - 预算超限时暂停 Pipeline
    - 所有状态变更写入 pipeline_step / pipeline_run 表

依赖关系：
    - app.pipelines.base : PipelineStep, StepResult
    - app.pipelines.context : PipelineContext
    - app.services.pipeline_service : CRUD + 工具函数
    - app.services.audit_service : 审计日志

模块拆分说明：
    为控制单文件行数，执行逻辑按职责拆分到同目录子模块，
    本文件作为 thin wrapper 保留全部公开 API：
        - _runner_progress : WebSocket 进度推送
        - _runner_metrics  : FMEA 监控指标记录
        - _runner_executor : Step 执行/重试/降级/产物持久化（Mixin）
"""

import logging

from app.pipelines.base import PipelineStep
from app.pipelines.context import PipelineContext
from app.pipelines._runner_control import (
    _abort_if_cancelled,
    _complete_pipeline,
    _fail_pipeline,
    _pause_for_confirmation,
    _pause_if_budget_exceeded,
    _prepare_resume,
    _progress_pct,
    _resume_filter,
)
from app.pipelines._runner_executor import MAX_RETRIES, _StepExecutionMixin
from app.pipelines._runner_metrics import _record_fmea_metric
from app.pipelines._runner_progress import _push_pipeline_progress
from app.services import pipeline_service

logger = logging.getLogger(__name__)

__all__ = [
    "PipelineRunner",
    "MAX_RETRIES",
    "_push_pipeline_progress",
    "_record_fmea_metric",
]


class PipelineRunner(_StepExecutionMixin):
    """流水线执行引擎。

    按依赖顺序执行 Step，处理缓存、重试、降级、暂停。

    Attributes:
        steps: 已注册的 Step 类列表（按执行顺序）。
        pipeline_name: 流水线名称（用于日志和审计）。
    """

    def __init__(self, pipeline_name: str, steps: list[type[PipelineStep]]):
        self.pipeline_name = pipeline_name
        self.steps = steps

    def run(self, ctx: PipelineContext) -> None:
        """执行流水线。

        按注册顺序逐个执行 Step，处理缓存命中、重试、降级、暂停。

        Args:
            ctx: 运行时上下文。

        Raises:
            RuntimeError: Pipeline 状态异常。
        """
        logger.info(
            "Pipeline '%s' started: run_id=%d, iteration_id=%d",
            self.pipeline_name,
            ctx.run.id,
            ctx.iteration_id,
        )

        resume_from_step = _prepare_resume(ctx)
        status = "waiting_for_user" if resume_from_step else "running"
        pipeline_service.update_run_status(
            db=ctx.db,
            run_id=ctx.run.id,
            status=status,
        )
        _push_pipeline_progress(ctx.run.id, "", status, 0.0, status)

        should_skip = _resume_filter(resume_from_step)
        total_steps = max(len(self.steps), 1)

        for step_idx, step_cls in enumerate(self.steps):
            step = step_cls()

            if should_skip(step.name):
                logger.info("Step '%s' skipped (resuming after pause)", step.name)
                continue

            # 协作式取消：API 端点写入 cancelled，Runner 在 Step 间检测（内部先 commit 再看）
            if _abort_if_cancelled(ctx, step, step_idx, total_steps, self.pipeline_name):
                return

            if not step.should_run(ctx):
                logger.info("Step '%s' skipped (should_run=False)", step.name)
                continue

            if _pause_if_budget_exceeded(ctx, step, step_idx, total_steps, self.pipeline_name):
                return

            _push_pipeline_progress(
                ctx.run.id,
                step.name,
                "running",
                _progress_pct(step_idx, total_steps),
                "running",
            )
            result = self._execute_step_with_retry(ctx, step)

            if result is None:
                _push_pipeline_progress(
                    ctx.run.id,
                    step.name,
                    "done",
                    _progress_pct(step_idx, total_steps, finished=True),
                    "running",
                )
                continue

            if result.pause_for_confirmation:
                _pause_for_confirmation(ctx, step, result, step_idx, total_steps, self.pipeline_name)
                return

            if not result.success:
                _fail_pipeline(ctx, step, result, step_idx, total_steps, self.pipeline_name)
                return

            if result.artifact_payload is not None:
                self._persist_artifact(ctx, step, result)

            _push_pipeline_progress(
                ctx.run.id,
                step.name,
                "degraded" if result.degraded else "done",
                _progress_pct(step_idx, total_steps, finished=True),
                "running",
            )

        _complete_pipeline(ctx, self.pipeline_name)
