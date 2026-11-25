"""DecisionDispatch 主循环 / 审核侧写 / 产物组装（G-8 B5f 从 `_step.execute` 拆出）。

`execute` 只保留「取产物 → 调三段 → 组装 StepResult」，三段各自可测：
1. `_run_verdicts`    逐条裁决：预算检查、未知动作跳过、规则查表累加 stats
2. `_create_skip_review` skip 任务自动开审核单（失败仅记日志，不阻断主流程）
3. `_build_payload`   产物 payload 口径（含可选 review_id）
"""

from typing import Any

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps.decision_dispatch._rules import get_action_rule

_STATS_KEYS: tuple[str, ...] = (
    "keep_count",
    "modify_count",
    "create_count",
    "locator_fix_count",
    "deprecate_count",
    "skip_count",
    "conflict_count",
)


def _new_stats() -> dict[str, int]:
    return dict.fromkeys(_STATS_KEYS, 0)


def _build_fp_index(fingerprint_list: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """case_id → 指纹，供 modify / deprecate 类构造器查历史。"""
    index: dict[int, dict[str, Any]] = {}
    for fp in fingerprint_list:
        cid = fp.get("case_id")
        if cid is not None:
            index[cid] = fp
    return index


def _dispatch_one(
    ctx: PipelineContext,
    verdict: dict[str, Any],
    cands: list[dict[str, Any]],
    fp_index: dict[int, dict[str, Any]],
    stats: dict[str, int],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """单条裁决 → (task, deprecation)；未知动作只累加 skip_count。"""
    action = verdict.get("action", "")
    case_id = verdict.get("case_id")
    rule = get_action_rule(action)
    if rule is None:
        logger.warning("未知裁决动作 action={}, case_id={}，跳过", action, case_id)
        stats["skip_count"] += 1
        return None, None

    task, deprecation = rule["handler"](
        case_id=case_id,
        reason=verdict.get("reason", ""),
        candidate_index=verdict.get("candidate_index"),
        cands=cands,
        fp_by_case_id=fp_index,
        db=ctx.db,
    )
    for stat_key in rule["stats"]:
        stats[stat_key] += 1
    return task, deprecation


def _run_verdicts(
    ctx: PipelineContext,
    verdicts: list[Any],
    cands: list[dict[str, Any]],
    fp_index: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int], bool]:
    """逐条裁决；预算耗尽即停并标记（已生成的任务保留）。"""
    generation_tasks: list[dict[str, Any]] = []
    deprecation_suggestions: list[dict[str, Any]] = []
    stats = _new_stats()
    budget_exhausted = False

    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        if not ctx.check_budget():
            logger.warning("DecisionDispatch 预算耗尽，已生成 {} 条任务后暂停", len(generation_tasks))
            budget_exhausted = True
            break
        task, deprecation = _dispatch_one(ctx, verdict, cands, fp_index, stats)
        if task is not None:
            generation_tasks.append(task)
        if deprecation is not None:
            deprecation_suggestions.append(deprecation)

    return generation_tasks, deprecation_suggestions, stats, budget_exhausted


def _skip_tasks(generation_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in generation_tasks if t.get("task_type") == "skip"]


def _add_skip_decision(db: Any, add_decision: Any, review_id: int, skip_task: dict[str, Any]) -> None:
    skip_reason = skip_task.get("skip_reason", "")
    add_decision(
        db=db,
        review_id=review_id,
        target_kind="case",
        target_id=skip_task.get("case_id") or 0,
        ai_verdict="modify" if "冲突" in skip_reason else "keep",
        ai_confidence=30,
        ai_reason=skip_reason,
    )


def _create_skip_review(ctx: PipelineContext, generation_tasks: list[dict[str, Any]]) -> int | None:
    """为 skip 任务自动建审核单；任一步失败仅记日志并返回已建 id（与原实现一致）。"""
    skip_tasks = _skip_tasks(generation_tasks)
    if not skip_tasks:
        return None

    review_id: int | None = None
    try:
        from app.services.review_service import add_decision, create_review, start_review

        review = create_review(db=ctx.db, iteration_id=ctx.iteration_id, kind="merged")
        review_id = review.id
        start_review(db=ctx.db, review_id=review_id)
        for skip_task in skip_tasks:
            _add_skip_decision(ctx.db, add_decision, review_id, skip_task)
    except Exception as e:
        logger.error("自动创建审核记录失败: {}", e)
    return review_id


def _build_payload(
    project_id: int,
    generation_tasks: list[dict[str, Any]],
    deprecation_suggestions: list[dict[str, Any]],
    stats: dict[str, int],
    review_id: int | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": project_id,
        "generation_tasks": generation_tasks,
        "deprecation_suggestions": deprecation_suggestions,
        "stats": stats,
        "total_tasks": len(generation_tasks),
        "total_deprecations": len(deprecation_suggestions),
    }
    if review_id is not None:
        payload["review_id"] = review_id
    return payload


__all__ = ["_build_fp_index", "_build_payload", "_create_skip_review", "_new_stats", "_run_verdicts"]
