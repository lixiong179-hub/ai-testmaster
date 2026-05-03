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

                for case_data in case_data_list:
                    try:
                        tp_id = tp.get("id")
                        score_info = score_map.get(tp_id, {})
                        lifecycle = case_data.get("lifecycle_status", "draft")
                        prior_score = score_info.get("score")
                        if score_info and score_info.get("grade") == "D":
                            lifecycle = "pending_review"  # 双重保障：QualityGate 已设置但此处再次确认

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
                            title=case_data.get("title", ""),
                            precondition=case_data.get("precondition", ""),
                            steps_json=steps_json,
                            expected_result=case_data.get("expected_result", ""),
                            priority=case_data.get("priority", 3),
                            case_type=case_data.get("case_type", "functional"),
                            lifecycle_status=lifecycle,
                            prior_quality_score=prior_score,
                        )
                        ctx.db.add(new_case)
                        ctx.db.flush()
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

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "persisted_case_ids": persisted_ids,
            "total_persisted": len(persisted_ids),
            "failed_persist": failed_persist,
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="persisted_case_ids",
            artifact_confidence=1.0,
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


def _build_score_map(scores_artifact: Optional[Dict[str, Any]]) -> Dict[int, Dict]:
    if not scores_artifact:
        return {}
    result = {}
    for score in scores_artifact.get("scores", []):
        tp_id = score.get("test_point_id")
        if tp_id:
            result[tp_id] = score
    return result


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
