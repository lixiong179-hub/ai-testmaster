from typing import Any, Dict, List, Optional

from loguru import logger

from app.pipelines.base import StepResult
from app.pipelines.context import PipelineContext


def _empty_stats() -> Dict[str, int]:
    return {
        "keep_count": 0, "modify_count": 0, "create_count": 0,
        "locator_fix_count": 0, "deprecate_count": 0,
        "skip_count": 0, "conflict_count": 0,
    }


def _dispatch_fallback(
    step_name: str,
    step_version: str,
    ctx: PipelineContext,
    error: Exception,
) -> Optional[StepResult]:
    merged = ctx.get_artifact("merged_verdicts")
    if merged is not None:
        logger.warning(
            "DecisionDispatch 执行异常但 merged_verdicts 可用, 返回空任务列表: {}",
            error,
        )
        return StepResult(
            success=True,
            artifact_payload={
                "project_id": merged.get("project_id", 0),
                "generation_tasks": [],
                "deprecation_suggestions": [],
                "stats": _empty_stats(),
                "total_tasks": 0,
                "total_deprecations": 0,
            },
            artifact_kind="generation_tasks",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": step_name,
                "version": step_version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )

    aligned = ctx.get_artifact("aligned_testpoints")
    if aligned is None:
        return StepResult(
            success=False,
            error=f"DecisionDispatch 降级失败: 缺少 aligned_testpoints ({error})",
            artifact_payload={
                "project_id": 0,
                "generation_tasks": [],
                "deprecation_suggestions": [],
                "stats": _empty_stats(),
                "total_tasks": 0,
                "total_deprecations": 0,
            },
            artifact_kind="generation_tasks",
            artifact_confidence=0.0,
            degraded=True,
        )

    aligned_tps = aligned.get("aligned_testpoints", [])
    fallback_tasks: List[Dict[str, Any]] = []
    for idx, entry in enumerate(aligned_tps):
        tp = entry.get("test_point", {}) if isinstance(entry, dict) else {}
        task = {
            "task_type": "create",
            "task_id": f"create_fallback_{idx}",
            "case_id": None,
            "candidate_description": tp.get("point", ""),
            "candidate_module": tp.get("module", ""),
            "candidate_priority": tp.get("priority", 3),
            "candidate_reason": "fallback: 由 aligned_testpoints 自动生成",
            "change_type": "added",
        }
        fallback_tasks.append(task)

    fallback_count = len(fallback_tasks)

    return StepResult(
        success=True,
        artifact_payload={
            "project_id": aligned.get("project_id", 0),
            "generation_tasks": fallback_tasks,
            "deprecation_suggestions": [],
            "stats": {
                "keep_count": 0, "modify_count": 0, "create_count": fallback_count,
                "locator_fix_count": 0, "deprecate_count": 0,
                "skip_count": 0, "conflict_count": 0,
            },
            "total_tasks": fallback_count,
            "total_deprecations": 0,
        },
        artifact_kind="generation_tasks",
        artifact_confidence=0.3,
        artifact_provenance={
            "step": step_name,
            "version": step_version,
            "degraded": True,
            "error": str(error),
            "fallback_source": "aligned_testpoints",
        },
        degraded=True,
    )
