"""Pipeline Step 执行器 Mixin 模块。

从 runner.py 拆分而来，负责单个 Step 的执行逻辑，包括：
    - 缓存命中检查与复用
    - 重试机制（MAX_RETRIES）
    - fallback 降级
    - 产物持久化

通过 Mixin 模式被 PipelineRunner 继承，保持 run() 主循环的简洁。
"""
import hashlib
import json
import logging
from typing import Optional

from app.models.pipeline import Artifact
from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.services import pipeline_service

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class _StepExecutionMixin:
    """Step 执行逻辑 Mixin。

    提供 Step 执行相关的缓存检查、重试、降级、产物持久化能力，
    供 PipelineRunner 通过继承复用，避免主类膨胀。

    依赖子类或同模块提供的 ctx / step 等运行时对象。
    """

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
