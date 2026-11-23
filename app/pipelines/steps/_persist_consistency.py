"""Persist Step 一致性校验。

校验持久化数量与预期数量的一致性，并验证 deprecation 旧用例状态。
批量查询旧用例避免循环内 N+1 查询。
"""

from typing import Any

from loguru import logger

from app.pipelines.context import PipelineContext


def _run_consistency_check(
    ctx: PipelineContext,
    persisted_ids: list[int],
) -> tuple[dict[str, Any], float]:
    """执行一致性校验，返回 (consistency_check, artifact_confidence)。

    校验逻辑：
    1. 从 generation_tasks 产物统计 expected_count；
    2. 批量查询 deprecation 旧用例状态（限制前 20 条，单次 .in_() 查询）；
    3. persisted/expected 比率超出 [0.8, 1.2] → is_consistent=False，confidence 降至 0.7。

    Args:
        ctx: Pipeline 上下文，提供 db 会话与产物访问。
        persisted_ids: 已持久化的用例 ID 列表。

    Returns:
        (consistency_check_dict, artifact_confidence) 二元组。
    """
    tasks_artifact = ctx.get_artifact("generation_tasks")
    expected_count, deprecation_suggestions = _extract_task_counts(tasks_artifact)
    persisted_count = len(persisted_ids)

    consistency_check: dict[str, Any] = {
        "expected_count": expected_count,
        "persisted_count": persisted_count,
        "deprecation_suggestions_count": len(deprecation_suggestions),
        "is_consistent": True,
        "warning": None,
    }

    if deprecation_suggestions:
        consistency_check["deprecation_verification"] = _verify_deprecation_cases(ctx, deprecation_suggestions)

    return consistency_check, _apply_ratio_check(consistency_check, expected_count, persisted_count)


def _extract_task_counts(tasks_artifact: dict[str, Any] | None) -> tuple[int, list]:
    """从 generation_tasks 产物取预期数量与 deprecation 建议列表。"""
    if not tasks_artifact:
        return 0, []
    generation_tasks = tasks_artifact.get("generation_tasks", [])
    deprecation_suggestions = tasks_artifact.get("deprecation_suggestions", [])
    expected_count = sum(1 for t in generation_tasks if t.get("task_type") in ("create", "modify", "locator_fix"))
    return expected_count, deprecation_suggestions


def _tally_deprecation_case(
    deprecation_check: dict[str, int], item: dict[str, Any], old_cases_map: dict[int, Any]
) -> None:
    """单条 deprecation 建议的校验计数（未带 case_id 的建议直接跳过）。"""
    case_id = item.get("case_id")
    if not case_id:
        return
    old_case = old_cases_map.get(case_id)
    if old_case is None:
        deprecation_check["not_found"] += 1
    elif old_case.lifecycle_status == "deprecated":
        deprecation_check["already_deprecated"] += 1
    deprecation_check["verified"] += 1


def _verify_deprecation_cases(ctx: PipelineContext, deprecation_suggestions: list) -> dict[str, int]:
    """校验 deprecation 对应旧用例状态；限前 20 条并单次 .in_() 批量查询。"""
    from app.models.test_case import TestCase as _TC

    check_items = deprecation_suggestions[:20]
    case_ids_to_check = [ds.get("case_id") for ds in check_items if ds.get("case_id") is not None]

    old_cases_map: dict[int, _TC] = {}
    if case_ids_to_check:
        old_cases = ctx.db.query(_TC).filter(_TC.id.in_(case_ids_to_check)).all()
        old_cases_map = {c.id: c for c in old_cases}

    deprecation_check = {"total": len(deprecation_suggestions), "verified": 0, "not_found": 0, "already_deprecated": 0}
    for item in check_items:
        _tally_deprecation_case(deprecation_check, item, old_cases_map)

    if deprecation_check["not_found"] > 0:
        logger.warning("deprecation 验证: {} 条旧用例未找到", deprecation_check["not_found"])
    return deprecation_check


def _apply_ratio_check(consistency_check: dict[str, Any], expected_count: int, persisted_count: int) -> float:
    """比率超出 [0.8, 1.2] 时标记不一致并把置信度降到 0.7。"""
    if expected_count <= 0:
        return 1.0

    ratio = persisted_count / expected_count
    if 0.8 <= ratio <= 1.2:
        return 1.0

    consistency_check["is_consistent"] = False
    consistency_check["warning"] = (
        f"持久化数量 ({persisted_count}) 与预期 ({expected_count}) 差异较大，比率: {ratio:.2f}"
    )
    logger.warning("一致性校验失败: {}", consistency_check["warning"])
    return 0.7
