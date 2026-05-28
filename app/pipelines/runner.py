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
"""
import asyncio
import hashlib
import json
import logging
from typing import List, Optional, Type

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.models.pipeline import Artifact, PipelineRun
from app.models.iteration import Iteration
from app.services import pipeline_service
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def _push_pipeline_progress(
    run_id: int,
    step_name: str,
    status: str,
    progress: float,
    pipeline_status: str,
) -> None:
    """通过 WebSocket 推送 Pipeline 进度（fire-and-forget）。

    在 Step 状态变更时调用，将进度信息推送到前端 WebSocket 客户端。
    推送失败不影响业务流程，仅记录警告日志。

    Args:
        run_id: Pipeline 运行 ID。
        step_name: 步骤名称，Pipeline 级别事件传空字符串。
        status: 当前步骤或 Pipeline 的状态。
        progress: 进度百分比（0-100）。
        pipeline_status: Pipeline 整体状态。
    """
    try:
        from app.services.push_service import get_push_service
        push_service = get_push_service()
        data = {
            "type": "pipeline_progress",
            "run_id": run_id,
            "step_name": step_name,
            "status": status,
            "progress": progress,
            "pipeline_status": pipeline_status,
        }
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(push_service.push(f"pipeline:{run_id}", data))
    except RuntimeError:
        logger.debug("No running event loop, skipping pipeline progress push")
    except Exception as e:
        logger.warning("Pipeline progress push failed: %s", e)


class PipelineRunner:
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

    def _execute_step_with_retry(
        self, ctx: PipelineContext, step: PipelineStep,
    ) -> Optional[StepResult]:
        """执行单个 Step（含缓存检查 + 重试 + 降级）。

        Args:
            ctx: 运行时上下文。
            step: Step 实例。

        Returns:
            StepResult（缓存命中返回 None）。
        """
        cache_key = step.cache_key(ctx)
        cached = pipeline_service.find_cached_step(db=ctx.db, cache_key=cache_key)
        if cached is not None:
            logger.info(
                "Step '%s' cache hit: step_id=%d", step.name, cached.id,
            )
            step_record = pipeline_service.create_step(
                db=ctx.db,
                run_id=ctx.run.id,
                step_name=step.name,
                step_version=step.version,
                cache_key=cache_key,
                input_artifact_ids=cached.input_artifact_ids,
            )
            pipeline_service.update_step_status(
                db=ctx.db,
                step_id=step_record.id,
                status="running",
            )
            pipeline_service.update_step_status(
                db=ctx.db,
                step_id=step_record.id,
                status="done",
                output_artifact_ids=list(cached.output_artifact_ids or []),
            )
            if cached.output_artifact_ids:
                for art_id in cached.output_artifact_ids:
                    artifact = ctx.db.get(Artifact, art_id)
                    if artifact:
                        ctx.set_artifact(artifact.kind, artifact)
            ctx.register_step_record(step.name, step_record)
            return None

        step_record = pipeline_service.create_step(
            db=ctx.db,
            run_id=ctx.run.id,
            step_name=step.name,
            step_version=step.version,
            cache_key=cache_key,
        )
        ctx.register_step_record(step.name, step_record)

        last_error: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                pipeline_service.update_step_status(
                    db=ctx.db, step_id=step_record.id, status="running",
                )

                result = step.execute(ctx)

                if result.artifact_payload is not None and not step.validate_output(result.artifact_payload):
                    raise ValueError(f"Step '{step.name}' output validation failed")

                pipeline_service.update_step_status(
                    db=ctx.db,
                    step_id=step_record.id,
                    status="degraded" if result.degraded else "done",
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "Step '%s' attempt %d/%d failed: %s",
                    step.name, attempt, MAX_RETRIES + 1, e,
                )
                pipeline_service.update_step_status(
                    db=ctx.db,
                    step_id=step_record.id,
                    status="failed",
                    error=str(e),
                )
                pipeline_service.increment_step_retried_count(
                    db=ctx.db, step_id=step_record.id,
                )

        logger.error(
            "Step '%s' all retries exhausted, calling fallback",
            step.name,
        )
        fallback_result = step.fallback(ctx, last_error)
        if fallback_result is not None:
            pipeline_service.update_step_status(
                db=ctx.db,
                step_id=step_record.id,
                status="degraded" if fallback_result.degraded else "done",
                degraded=fallback_result.degraded,
            )
            return fallback_result

        pipeline_service.update_step_status(
            db=ctx.db,
            step_id=step_record.id,
            status="failed",
            error=str(last_error),
        )
        return StepResult(success=False, error=str(last_error))

    def _persist_artifact(
        self, ctx: PipelineContext, step: PipelineStep, result: StepResult,
    ) -> None:
        """持久化 Step 产物。

        Args:
            ctx: 运行时上下文。
            step: Step 实例。
            result: Step 执行结果。
        """
        content_hash = hashlib.sha256(
            json.dumps(result.artifact_payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

        artifact = pipeline_service.create_artifact(
            db=ctx.db,
            run_id=ctx.run.id,
            kind=result.artifact_kind,
            content_hash=content_hash,
            payload=result.artifact_payload,
            confidence=result.artifact_confidence,
            provenance=result.artifact_provenance,
        )
        ctx.set_artifact(result.artifact_kind, artifact)

        step_record = ctx.get_step_record(step.name)
        if step_record is not None:
            output_ids = list(step_record.output_artifact_ids or []) + [artifact.id]
            pipeline_service.update_step_output_artifact_ids(
                db=ctx.db, step_id=step_record.id, artifact_ids=output_ids,
            )


def _record_fmea_metric(
    ctx: PipelineContext,
    metric_name: str,
    *,
    step_name: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """在 Pipeline 运行中记录 FMEA 监控指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        project_id = ctx._cached_project_id
        if project_id is None and ctx.iteration_id:
            iteration = ctx.db.query(Iteration).filter(
                Iteration.id == ctx.iteration_id,
            ).first()
            if iteration:
                project_id = iteration.project_id
            ctx._cached_project_id = project_id
        record_metric(
            metric_name,
            project_id=project_id,
            iteration_id=ctx.iteration_id,
            run_id=ctx.run.id,
            step_name=step_name,
            detail=detail,
        )
    except Exception as e:
        logger.warning("FMEA metric recording failed: %s", e)
