"""S13 Persist — 用例持久化 Step

将生成的测试用例写入数据库，
设置 lifecycle_status、关联测试点、生成用例编号。
"""
import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class Persist(PipelineStep):
    """用例持久化 Step — 将生成的用例落库。"""

    name: ClassVar[str] = "persist"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases", "quality_scores"]
    produces: ClassVar[List[str]] = ["persisted_case_ids"]

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
                        lifecycle = case_data.get("lifecycle_status", "draft")
                        if grade == "D":
                            lifecycle = "pending_review"

                        case_no = _generate_case_no(ctx, project_id)

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
                            case_type=case_data.get("case_type", "functional"),
                            lifecycle_status=lifecycle,
                            prior_quality_score=prior_score,
                            parent_case_id=parent_case_id,
                            ai_change_type=ai_change_type,
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
            for ds in deprecation_suggestions[:20]:  # 最多检查20条
                case_id = ds.get("case_id")
                if case_id:
                    old_case = ctx.db.query(_TC).filter(_TC.id == case_id).first()
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
        ctx.db.add(TestStep(
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


def _generate_case_no(ctx: PipelineContext, project_id: int) -> str:
    from app.models.test_case import TestCase

    # 使用 SELECT ... FOR UPDATE 加行级锁，防止并发生成重复编号
    last_case = ctx.db.query(TestCase).filter(
        TestCase.project_id == project_id,
    ).order_by(TestCase.id.desc()).with_for_update().first()

    next_num = 1
    if last_case and last_case.case_no:
        try:
            prefix = "TC-"
            num_part = last_case.case_no.replace(prefix, "")
            next_num = int(num_part.split("-")[-1]) + 1 if "-" in num_part else int(num_part) + 1
        except (ValueError, IndexError):
            next_num = 1

    return f"TC-{project_id:03d}-{next_num:04d}"
