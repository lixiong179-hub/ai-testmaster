"""Persist Step 用例写入主循环。

在生命周期锁保护下，将生成的用例逐条写入数据库，
推导 parent_case_id / ai_change_type，并关联测试步骤。
"""
import threading
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.pipelines.context import PipelineContext
from app.services.case_number_service import CaseNumberService
from app.pipelines.steps._persist_utils import (
    _parse_datetime_field,
    _persist_case_steps,
    _serialize_json_field,
)


def _derive_task_fields(task: Optional[Dict[str, Any]]) -> Tuple[Optional[int], Optional[str]]:
    """从 entry.task 推导 parent_case_id 与 ai_change_type。

    Args:
        task: 任务信息字典，可能为 None。

    Returns:
        (parent_case_id, ai_change_type) 二元组。
    """
    if not task:
        return None, None

    task_type = task.get("task_type", "")
    parent_case_id = task.get("case_id")  # 原用例ID（modify/locator_fix 模式）
    ai_change_type: Optional[str] = None
    if task_type == "modify":
        ai_change_type = "modified"
    elif task_type == "locator_fix":
        ai_change_type = "locator_fix"
    elif task_type == "create":
        ai_change_type = "added"

    if task_type == "modify" and parent_case_id is None:
        logger.warning(
            "modify 任务缺少 parent_case_id: task_id={}",
            task.get("task_id", "unknown"),
        )

    return parent_case_id, ai_change_type


def _resolve_quality_grade(
    case_data: Dict[str, Any],
    score_map: Dict[str, Dict],
) -> Tuple[Optional[Any], Optional[str]]:
    """解析用例的 prior_quality_score 与 quality_grade。

    优先从 case_data 取 QualityGate 直接写入的分数（解决同 tp 多用例覆盖问题）；
    其次回退到 score_map。quality_grade 优先由 grade_status 映射
    （A=passed/B=warning/C=pending_review/D=rejected）。
    向后兼容：映射失败时保留分数映射的 grade，不阻断入库。

    Args:
        case_data: 单条用例数据。
        score_map: case_title -> score_info 的 fallback 映射。

    Returns:
        (prior_score, grade) 二元组。
    """
    prior_score = case_data.get("prior_quality_score")
    grade = case_data.get("prior_quality_grade")
    if prior_score is None:
        score_info = score_map.get(case_data.get("title", ""), {})
        prior_score = score_info.get("score")
        grade = score_info.get("grade") if score_info else None
    # Task 17.3: quality_grade 优先由 grade_status 映射
    try:
        from app.services.case_quality.quality_scoring_service import (
            QualityScoringService,
        )
        from app.services.quality.grade import grade_status_to_letter
        mapped = grade_status_to_letter(
            QualityScoringService.grade_status(case_data)
        )
        if mapped:
            grade = mapped
    except Exception as e:
        logger.debug(
            "grade_status 映射失败，保留分数映射 grade={}: {}",
            grade, e,
        )
    return prior_score, grade


def _persist_generated_cases(
    ctx: PipelineContext,
    generated_cases: List[Dict[str, Any]],
    project_id: Optional[int],
    score_map: Dict[str, Dict],
    has_ui: bool,
    lifecycle_lock: threading.Lock,
) -> Tuple[List[int], int]:
    """执行用例持久化主循环，返回 (persisted_ids, failed_persist)。

    在类级线程锁保护下启用 lifecycle_transition，逐条构建 TestCase 并写入，
    失败的用例计入 failed_persist 但不中断整体流程。

    Args:
        ctx: Pipeline 上下文，提供 db 会话与 iteration_id。
        generated_cases: 生成的用例条目列表。
        project_id: 项目 ID。
        score_map: case_title -> score_info 的 fallback 映射。
        has_ui: 是否包含 UI 上下文（影响步骤 locator 字段）。
        lifecycle_lock: 生命周期状态保护锁。

    Returns:
        (persisted_case_ids, failed_persist_count) 二元组。
    """
    from app.models.test_case import TestCase, enable_lifecycle_transition

    persisted_ids: List[int] = []
    failed_persist = 0

    # 使用类级线程锁保护全局生命周期状态，防止并发任务互相干扰
    with lifecycle_lock:
        enable_lifecycle_transition()
        try:
            for entry in generated_cases:
                if entry.get("status") != "success":
                    continue

                tp = entry.get("test_point", {})
                case_data_list = entry.get("case_data", [])

                # 从 entry 中获取 task 信息，推导 ai_change_type 和 parent_case_id
                parent_case_id, ai_change_type = _derive_task_fields(entry.get("task"))

                for case_data in case_data_list:
                    try:
                        tp_id = tp.get("id")
                        prior_score, grade = _resolve_quality_grade(case_data, score_map)

                        lifecycle = case_data.get("lifecycle_status", "draft")
                        if grade == "D":
                            lifecycle = "pending_review"

                        case_no = CaseNumberService.generate(project_id, ctx.db)

                        steps_json = case_data.get("steps", [])
                        if isinstance(steps_json, list):
                            steps_json = [
                                s if isinstance(s, dict) else {"step": str(s)}
                                for s in steps_json
                            ]
                        else:
                            steps_json = []

                        new_case = TestCase(
                            case_no=case_no,
                            project_id=project_id,
                            test_point_id=tp_id,
                            module=case_data.get("module", tp.get("module", "")),
                            title=case_data.get("title") or tp.get("point", "测试用例") or "(无标题)",
                            precondition=case_data.get("precondition", ""),
                            steps_json=steps_json,
                            expected_result=case_data.get("expected_result", ""),
                            priority=case_data.get("priority", 3),
                            case_type=case_data.get("case_type", "ui_automation"),
                            lifecycle_status=lifecycle,
                            prior_quality_score=prior_score,
                            quality_grade=grade,
                            parent_case_id=parent_case_id,
                            ai_change_type=ai_change_type,
                            depends_on=case_data.get("depends_on"),
                            anchor_step=case_data.get("anchor_step"),
                            fallback_steps=_serialize_json_field(case_data.get("fallback_steps")),
                            setup_api_calls=_serialize_json_field(case_data.get("setup_api_calls")),
                            execution_verified=case_data.get("execution_verified"),
                            element_verified_ratio=case_data.get("element_verified_ratio"),
                            execution_failure_type=case_data.get("execution_failure_type"),
                            last_verified_at=_parse_datetime_field(
                                case_data.get("last_verified_at"),
                            ),
                        )
                        ctx.db.add(new_case)
                        ctx.db.flush()
                        _persist_case_steps(
                            ctx,
                            new_case.id,
                            steps_json,
                            has_ui,
                        )
                        persisted_ids.append(new_case.id)

                    except Exception as e:
                        failed_persist += 1
                        logger.error("用例持久化失败: {}", e)
                        continue

            ctx.db.flush()
        finally:
            from app.models.test_case import disable_lifecycle_transition
            disable_lifecycle_transition()

    return persisted_ids, failed_persist
