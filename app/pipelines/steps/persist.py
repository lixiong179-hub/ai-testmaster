"""S13 Persist — 用例持久化 Step

将生成的测试用例写入数据库，
设置 lifecycle_status、关联测试点、生成用例编号。
"""
import json
import threading
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.services.case_number_service import CaseNumberService


def _serialize_json_field(value: Any) -> Optional[str]:
    """将列表或已序列化的字符串统一为 JSON 字符串。

    Args:
        value: 列表或已序列化的字符串。

    Returns:
        JSON 字符串或 None。
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return None


def _parse_datetime_field(value: Any) -> Optional[datetime]:
    """将 ISO 字符串或 datetime 对象统一为 datetime 对象。

    用于解析 case_data 中的 last_verified_at 字段（由 ExecutionValidation
    Step 写入）。支持 ISO 8601 字符串和 datetime 对象，非法值返回 None。

    Args:
        value: ISO 字符串、datetime 对象或 None。

    Returns:
        datetime 对象或 None。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("last_verified_at 非法 ISO 字符串: {}，已置为 None", value)
            return None
    logger.warning(
        "last_verified_at 非法类型: {}，已置为 None", type(value).__name__,
    )
    return None


class Persist(PipelineStep):
    """用例持久化 Step — 将生成的用例落库。"""

    name: ClassVar[str] = "persist"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases", "quality_scores"]
    produces: ClassVar[List[str]] = ["persisted_case_ids"]
    # 类级初始化避免懒初始化的 TOCTOU 竞态：
    # 若在方法内 `if not hasattr(...): Lock()` 判断与赋值之间可能两个线程同时进入，
    # 创建两个不同的 Lock 实例导致锁失效。
    _lifecycle_lock: ClassVar[threading.Lock] = threading.Lock()

    def should_run(self, ctx: PipelineContext) -> bool:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        # 持久化步骤不应缓存，每次都需实际写入数据库
        return ""

    def execute(self, ctx: PipelineContext) -> StepResult:
        cases_artifact = ctx.get_artifact("generated_cases")
        scores_artifact = ctx.get_artifact("quality_scores")

        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        generated_cases = cases_artifact.get("generated_cases", [])
        project_id = cases_artifact.get("project_id")
        score_map = _build_score_map(scores_artifact)

        persisted_ids = []
        failed_persist = 0

        from app.models.test_case import TestCase, enable_lifecycle_transition

        # 使用类级线程锁保护全局生命周期状态，防止并发任务互相干扰
        with Persist._lifecycle_lock:
            enable_lifecycle_transition()
            try:
                for entry in generated_cases:
                    if entry.get("status") != "success":
                        continue

                    tp = entry.get("test_point", {})
                    case_data_list = entry.get("case_data", [])

                    # 从 entry 中获取 task 信息，推导 ai_change_type 和 parent_case_id
                    task = entry.get("task")
                    parent_case_id: Optional[int] = None
                    ai_change_type: Optional[str] = None
                    if task:
                        task_type = task.get("task_type", "")
                        parent_case_id = task.get("case_id")  # 原用例ID（modify/locator_fix 模式）
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

                    for case_data in case_data_list:
                        try:
                            tp_id = tp.get("id")
                            # 优先从 case_data 取 QualityGate 直接写入的分数（解决同 tp 多用例覆盖问题）
                            prior_score = case_data.get("prior_quality_score")
                            grade = case_data.get("prior_quality_grade")
                            if prior_score is None:
                                score_info = score_map.get(case_data.get("title", ""), {})
                                prior_score = score_info.get("score")
                                grade = score_info.get("grade") if score_info else None
                            # Task 17.3: quality_grade 优先由 grade_status 映射
                            # （A=passed/B=warning/C=pending_review/D=rejected）。
                            # 向后兼容：映射失败时保留分数映射的 grade，不阻断入库。
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
                                cases_artifact.get("has_ui", False),
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

        if not persisted_ids:
            return StepResult(
                success=False,
                error="所有用例持久化失败",
            )

        # --- 一致性校验 ---
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

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "persisted_case_ids": persisted_ids,
            "total_persisted": len(persisted_ids),
            "failed_persist": failed_persist,
            "consistency_check": consistency_check,
        }

        enable_posterior = ctx.get_config("ENABLE_POSTERIOR_SCORING", False)
        if not enable_posterior:
            from app.models.pipeline_config import PipelineConfig
            config_row = ctx.db.query(PipelineConfig).first()
            if config_row and getattr(config_row, "enable_posterior_scoring", False):
                enable_posterior = True

        if enable_posterior:
            try:
                from app.services.posterior_quality_service import compute_and_persist_posterior
                posterior_result = compute_and_persist_posterior(ctx.db, project_id)
                payload["posterior_scoring"] = posterior_result
                logger.info(
                    "后验评分已触发: project_id={}, score={}",
                    project_id,
                    posterior_result.get("posterior_quality_score"),
                )
            except Exception as e:
                logger.error("后验评分触发失败: project_id={}, error={}", project_id, e)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="persisted_case_ids",
            artifact_confidence=artifact_confidence_val,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "persisted_count": len(persisted_ids),
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "persisted_case_ids" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"用例持久化降级: {error}",
            degraded=True,
        )


def _build_score_map(scores_artifact: Optional[Dict[str, Any]]) -> Dict[str, Dict]:
    """构建 case_title -> score_info 映射（fallback 用）。

    主路径优先从 case_data 取 QualityGate 直接写入的分数，
    此函数仅在 case_data 缺少分数时作为 fallback。
    使用 case_title 而非 tp_id 作为键，避免同一测试点多用例覆盖。
    """
    if not scores_artifact:
        return {}
    result = {}
    for score in scores_artifact.get("scores", []):
        title = score.get("case_title", "")
        if title:
            result[title] = score
    return result


def _persist_case_steps(
    ctx: PipelineContext,
    case_id: int,
    steps_json: List[Dict[str, Any]],
    has_ui: bool,
) -> None:
    from app.models.test_case import TestStep

    steps_to_add = []
    for index, step_data in enumerate(steps_json, start=1):
        action = (
            step_data.get("action")
            or step_data.get("step")
            or step_data.get("description")
            or ""
        )
        expected = (
            step_data.get("expected")
            or step_data.get("expected_result")
            or step_data.get("expect")
            or ""
        )
        has_locator = int(step_data.get("has_locator", 0)) if has_ui else 0
        locator_status = step_data.get("locator_status") if has_ui else "pending"
        steps_to_add.append(TestStep(
            test_case_id=case_id,
            step_number=index,
            action=str(action),
            expected_result=str(expected),
            has_locator=has_locator,
            locator_status=locator_status or "pending",
            action_type=step_data.get("action_type"),
            input_value=step_data.get("input_value"),
            target_element=step_data.get("target_element"),
        ))

    if steps_to_add:
        ctx.db.add_all(steps_to_add)
