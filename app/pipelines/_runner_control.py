"""PipelineRunner 主循环控制件（G-8 B5g 从 `PipelineRunner.run` 拆出）。

`run` 原先在一个 90 行循环体内混了 6 类控制流（续跑过滤 / 取消 / 预算 / 暂停确认 / 失败 / 完成），
这里按控制点拆成单一职责函数，返回值的语义只有两种：**是否终止整条流水线** 或 **跳过当前 Step**。

约定：
- `_prepare_resume` / `_resume_filter`：断点续跑只重放 resume 之后（含）的 Step
- `_abort_if_cancelled` / `_pause_if_budget_exceeded` / `_pause_for_confirmation` / `_fail_pipeline`：终止型
- `_complete_pipeline`：正常收尾
"""

import logging
from collections.abc import Callable
from typing import Any

from app.models.pipeline import PipelineRun
from app.pipelines._runner_metrics import _record_fmea_metric
from app.pipelines._runner_progress import _push_pipeline_progress
from app.pipelines.context import PipelineContext
from app.services import pipeline_service
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)


def _progress_pct(step_idx: int, total_steps: int, finished: bool = False) -> float:
    """Step 进度百分比：finished=True 表示该 Step 已完成，否则表示刚开始。"""
    numerator = step_idx + 1 if finished else step_idx
    return round((numerator / total_steps) * 100, 1)


def _prepare_resume(ctx: PipelineContext) -> str | None:
    """读取并清空 pause_payload 中的续跑锚点；有锚点时记一条 FMEA 恢复指标。"""
    current_run = ctx.db.query(PipelineRun).filter(PipelineRun.id == ctx.run.id).first()
    if not (current_run and current_run.pause_payload and isinstance(current_run.pause_payload, dict)):
        return None

    resume_from_step = current_run.pause_payload.get("step_name")
    current_run.pause_payload = None
    ctx.db.flush()
    if resume_from_step is not None:
        _record_fmea_metric(
            ctx,
            "pipeline_recovery",
            step_name=resume_from_step,
            detail={"reason": "Pipeline resumed after pause"},
        )
    return resume_from_step


def _resume_filter(resume_from_step: str | None) -> Callable[[str], bool]:
    """构造 should_skip(step_name)：resume 锚点之前的 Step 跳过，命中锚点后全部放行。"""
    state = {"reached": resume_from_step is None}

    def should_skip(step_name: str) -> bool:
        if state["reached"]:
            return False
        if step_name == resume_from_step:
            state["reached"] = True
            return False
        return True

    return should_skip


def _abort_if_cancelled(ctx: PipelineContext, step: Any, step_idx: int, total_steps: int, pipeline_name: str) -> bool:
    """协作式取消：先 commit 让 REPEATABLE READ 能看到其他事务写入的 cancelled。"""
    ctx.db.commit()
    fresh_run = ctx.db.query(PipelineRun).filter(PipelineRun.id == ctx.run.id).first()
    if not (fresh_run and fresh_run.status == "cancelled"):
        return False
    logger.info(
        "Pipeline '%s' cancelled at step '%s': run_id=%d",
        pipeline_name,
        step.name,
        ctx.run.id,
    )
    _push_pipeline_progress(ctx.run.id, step.name, "cancelled", _progress_pct(step_idx, total_steps), "cancelled")
    return True


def _pause_if_budget_exceeded(
    ctx: PipelineContext, step: Any, step_idx: int, total_steps: int, pipeline_name: str
) -> bool:
    """Token 预算耗尽 → 置 waiting_for_user 并终止（可续跑）。"""
    if ctx.check_budget():
        return False
    logger.warning(
        "Pipeline '%s' paused: token budget exceeded at step '%s'",
        pipeline_name,
        step.name,
    )
    _record_fmea_metric(
        ctx,
        "token_budget_exceeded",
        step_name=step.name,
        detail={"reason": "Token budget exceeded"},
    )
    pipeline_service.update_run_status(
        db=ctx.db,
        run_id=ctx.run.id,
        status="waiting_for_user",
        error=f"Token budget exceeded at step '{step.name}'",
    )
    _push_pipeline_progress(
        ctx.run.id,
        step.name,
        "waiting_for_user",
        _progress_pct(step_idx, total_steps),
        "waiting_for_user",
    )
    ctx.db.commit()
    return True


def _pause_for_confirmation(
    ctx: PipelineContext, step: Any, result: Any, step_idx: int, total_steps: int, pipeline_name: str
) -> None:
    """Step 请求确认（低置信度等）→ 落 pause_payload 并终止。"""
    pause_info = ctx.get_pause_info() or {
        "reason": result.confirmation_reason or "Step paused",
        "step_name": step.name,
        "schema": getattr(result, "confirmation_schema", None),
        "paused_at": utcnow().isoformat(),
    }
    logger.info(
        "Pipeline '%s' paused at step '%s': reason='%s'",
        pipeline_name,
        step.name,
        pause_info.get("reason"),
    )
    _record_fmea_metric(
        ctx,
        "low_confidence_pause",
        step_name=step.name,
        detail={
            "reason": pause_info.get("reason", ""),
            "confidence": result.artifact_confidence,
        },
    )
    pipeline_service.update_run_status(db=ctx.db, run_id=ctx.run.id, status="waiting_for_user")
    current_run_obj = ctx.db.query(PipelineRun).filter(PipelineRun.id == ctx.run.id).first()
    if current_run_obj:
        current_run_obj.pause_payload = pause_info
    ctx.db.commit()
    _push_pipeline_progress(
        ctx.run.id,
        step.name,
        "waiting_for_user",
        _progress_pct(step_idx, total_steps),
        "waiting_for_user",
    )


def _fail_pipeline(
    ctx: PipelineContext, step: Any, result: Any, step_idx: int, total_steps: int, pipeline_name: str
) -> None:
    """Step 返回失败 → 置 failed 并终止。"""
    logger.error(
        "Pipeline '%s' failed at step '%s': %s",
        pipeline_name,
        step.name,
        result.error,
    )
    pipeline_service.update_run_status(
        db=ctx.db,
        run_id=ctx.run.id,
        status="failed",
        error=f"Step '{step.name}' failed: {result.error}",
    )
    _push_pipeline_progress(
        ctx.run.id,
        step.name,
        "failed",
        _progress_pct(step_idx, total_steps, finished=True),
        "failed",
    )
    ctx.db.commit()


def _complete_pipeline(ctx: PipelineContext, pipeline_name: str) -> None:
    pipeline_service.update_run_status(db=ctx.db, run_id=ctx.run.id, status="completed")
    _push_pipeline_progress(ctx.run.id, "", "completed", 100.0, "completed")
    ctx.db.commit()
    logger.info("Pipeline '%s' completed: run_id=%d", pipeline_name, ctx.run.id)


__all__ = [
    "_abort_if_cancelled",
    "_complete_pipeline",
    "_fail_pipeline",
    "_pause_for_confirmation",
    "_pause_if_budget_exceeded",
    "_prepare_resume",
    "_progress_pct",
    "_resume_filter",
]
