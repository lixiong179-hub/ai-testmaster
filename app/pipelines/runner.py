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
from typing import List, Optional, Type

from app.models.pipeline import PipelineRun
from app.pipelines.base import PipelineStep
from app.pipelines.context import PipelineContext
from app.pipelines._runner_executor import MAX_RETRIES, _StepExecutionMixin
from app.pipelines._runner_metrics import _record_fmea_metric
from app.pipelines._runner_progress import _push_pipeline_progress
from app.services import pipeline_service
from app.utils.db_time import utcnow

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

    def __init__(self, pipeline_name: str, steps: List[Type[PipelineStep]]):
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
            self.pipeline_name, ctx.run.id, ctx.iteration_id,
        )

        current_run = (
            ctx.db.query(PipelineRun)
            .filter(PipelineRun.id == ctx.run.id)
            .first()
        )
        resume_from_step: Optional[str] = None
        if current_run and current_run.pause_payload and isinstance(current_run.pause_payload, dict):
            resume_from_step = current_run.pause_payload.get("step_name")
            current_run.pause_payload = None
            ctx.db.flush()

        if resume_from_step is not None:
            _record_fmea_metric(
                ctx, "pipeline_recovery",
                step_name=resume_from_step,
                detail={"reason": "Pipeline resumed after pause"},
            )

        status = "waiting_for_user" if resume_from_step else "running"
        pipeline_service.update_run_status(
            db=ctx.db, run_id=ctx.run.id, status=status,
        )
        _push_pipeline_progress(ctx.run.id, "", status, 0.0, status)

        skip_mode = resume_from_step is not None
        reached_resume = False

        total_steps = max(len(self.steps), 1)
        for step_idx, step_cls in enumerate(self.steps):
            step = step_cls()

            if skip_mode and not reached_resume:
                if step.name == resume_from_step:
                    reached_resume = True
                else:
                    logger.info("Step '%s' skipped (resuming after pause)", step.name)
                    continue

            # 协作式取消检查：API 端点写入 cancelled 状态，Runner 在 Step 间检测
            # 先 commit 当前事务，确保在 REPEATABLE READ 隔离级别下能看到其他事务的更新
            ctx.db.commit()
            fresh_run = (
                ctx.db.query(PipelineRun)
                .filter(PipelineRun.id == ctx.run.id)
                .first()
            )
            if fresh_run and fresh_run.status == "cancelled":
                logger.info(
                    "Pipeline '%s' cancelled at step '%s': run_id=%d",
                    self.pipeline_name, step.name, ctx.run.id,
                )
                _push_pipeline_progress(
                    ctx.run.id, step.name, "cancelled",
                    round((step_idx / total_steps) * 100, 1), "cancelled",
                )
                return

            if not step.should_run(ctx):
                logger.info("Step '%s' skipped (should_run=False)", step.name)
                continue

            if not ctx.check_budget():
                logger.warning(
                    "Pipeline '%s' paused: token budget exceeded at step '%s'",
                    self.pipeline_name, step.name,
                )
                _record_fmea_metric(
                    ctx, "token_budget_exceeded",
                    step_name=step.name,
                    detail={"reason": "Token budget exceeded"},
                )
                pipeline_service.update_run_status(
                    db=ctx.db, run_id=ctx.run.id, status="waiting_for_user",
                    error=f"Token budget exceeded at step '{step.name}'",
                )
                _push_pipeline_progress(
                    ctx.run.id, step.name, "waiting_for_user",
                    round((step_idx / total_steps) * 100, 1), "waiting_for_user",
                )
                ctx.db.commit()
                return

            _push_pipeline_progress(
                ctx.run.id, step.name, "running",
                round((step_idx / total_steps) * 100, 1), "running",
            )
            result = self._execute_step_with_retry(ctx, step)

            if result is None:
                _push_pipeline_progress(
                    ctx.run.id, step.name, "done",
                    round(((step_idx + 1) / total_steps) * 100, 1), "running",
                )
                continue

            if result.pause_for_confirmation:
                pause_info = ctx.get_pause_info() or {
                    "reason": result.confirmation_reason or "Step paused",
                    "step_name": step.name,
                    "schema": getattr(result, "confirmation_schema", None),
                    "paused_at": utcnow().isoformat(),
                }
                logger.info(
                    "Pipeline '%s' paused at step '%s': reason='%s'",
                    self.pipeline_name, step.name, pause_info.get("reason"),
                )
                _record_fmea_metric(
                    ctx, "low_confidence_pause",
                    step_name=step.name,
                    detail={
                        "reason": pause_info.get("reason", ""),
                        "confidence": result.artifact_confidence,
                    },
                )
                pipeline_service.update_run_status(
                    db=ctx.db, run_id=ctx.run.id, status="waiting_for_user",
                )
                current_run_obj = ctx.db.query(PipelineRun).filter(
                    PipelineRun.id == ctx.run.id
                ).first()
                if current_run_obj:
                    current_run_obj.pause_payload = pause_info
                ctx.db.commit()
                _push_pipeline_progress(
                    ctx.run.id, step.name, "waiting_for_user",
                    round((step_idx / total_steps) * 100, 1), "waiting_for_user",
                )
                return

            if not result.success:
                logger.error(
                    "Pipeline '%s' failed at step '%s': %s",
                    self.pipeline_name, step.name, result.error,
                )
                pipeline_service.update_run_status(
                    db=ctx.db, run_id=ctx.run.id, status="failed",
                    error=f"Step '{step.name}' failed: {result.error}",
                )
                _push_pipeline_progress(
                    ctx.run.id, step.name, "failed",
                    round(((step_idx + 1) / total_steps) * 100, 1), "failed",
                )
                ctx.db.commit()
                return

            if result.artifact_payload is not None:
                self._persist_artifact(ctx, step, result)

            _push_pipeline_progress(
                ctx.run.id, step.name,
                "degraded" if result.degraded else "done",
                round(((step_idx + 1) / total_steps) * 100, 1), "running",
            )

        pipeline_service.update_run_status(
            db=ctx.db, run_id=ctx.run.id, status="completed",
        )
        _push_pipeline_progress(ctx.run.id, "", "completed", 100.0, "completed")
        ctx.db.commit()

        logger.info(
            "Pipeline '%s' completed: run_id=%d",
            self.pipeline_name, ctx.run.id,
        )
