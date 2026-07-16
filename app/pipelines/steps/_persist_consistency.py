"""Persist Step 一致性校验。

校验持久化数量与预期数量的一致性，并验证 deprecation 旧用例状态。
批量查询旧用例避免循环内 N+1 查询。
"""
from typing import Any, Dict, List, Tuple

from loguru import logger

from app.pipelines.context import PipelineContext


def _run_consistency_check(
    ctx: PipelineContext,
    persisted_ids: List[int],
) -> Tuple[Dict[str, Any], float]:
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

    expected_count = 0
    deprecation_suggestions: list = []
    deprecation_suggestions_count = 0

    if tasks_artifact:
        generation_tasks = tasks_artifact.get("generation_tasks", [])
        deprecation_suggestions = tasks_artifact.get("deprecation_suggestions", [])
        deprecation_suggestions_count = len(deprecation_suggestions)
        expected_count = sum(
            1 for t in generation_tasks
            if t.get("task_type") in ("create", "modify", "locator_fix")
        )

    persisted_count = len(persisted_ids)

    consistency_check = {
        "expected_count": expected_count,
        "persisted_count": persisted_count,
        "deprecation_suggestions_count": deprecation_suggestions_count,
        "is_consistent": True,
        "warning": None,
    }

    # 验证 deprecation 对应的旧用例状态
    if deprecation_suggestions:
        from app.models.test_case import TestCase as _TC
        deprecation_check: dict = {
            "total": len(deprecation_suggestions),
            "verified": 0,
            "not_found": 0,
            "already_deprecated": 0,
        }
        # 批量查询：收集 case_id 后一次 .in_() 查询，避免循环内 N+1 查询
        check_items = deprecation_suggestions[:20]
        case_ids_to_check = [
            ds.get("case_id") for ds in check_items
            if ds.get("case_id") is not None
        ]
        old_cases_map: Dict[int, _TC] = {}
        if case_ids_to_check:
            old_cases = ctx.db.query(_TC).filter(
                _TC.id.in_(case_ids_to_check)
            ).all()
            old_cases_map = {c.id: c for c in old_cases}

        for ds in check_items:
            case_id = ds.get("case_id")
            if case_id:
                old_case = old_cases_map.get(case_id)
                if old_case is None:
                    deprecation_check["not_found"] += 1
                elif old_case.lifecycle_status == "deprecated":
                    deprecation_check["already_deprecated"] += 1
                deprecation_check["verified"] += 1
        consistency_check["deprecation_verification"] = deprecation_check
        if deprecation_check["not_found"] > 0:
            logger.warning(
                "deprecation 验证: {} 条旧用例未找到",
                deprecation_check["not_found"],
            )

    artifact_confidence_val = 1.0

    if expected_count > 0:
        ratio = persisted_count / expected_count if expected_count > 0 else 1.0
        if ratio < 0.8 or ratio > 1.2:
            consistency_check["is_consistent"] = False
            consistency_check["warning"] = (
                f"持久化数量 ({persisted_count}) 与预期 ({expected_count}) 差异较大，比率: {ratio:.2f}"
            )
            logger.warning("一致性校验失败: {}", consistency_check["warning"])
            artifact_confidence_val = min(artifact_confidence_val, 0.7)

    return consistency_check, artifact_confidence_val
