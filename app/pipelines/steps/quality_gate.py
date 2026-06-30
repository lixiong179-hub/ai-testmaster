import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps._qg_coverage import (
    _build_tp_from_task,
    _classify_case_type_local,
    _compute_module_coverage,
    _compute_ui_element_coverage,
)
from app.pipelines.steps._regeneration import (
    _collect_d_grade_cases,
    _regenerate_d_cases,
)
from app.pipelines.steps._signal_scoring import (
    _check_user_confirmed,
    _compute_analyzer_score,
    _compute_prior_score,
    _score_to_grade,
)
from app.pipelines.steps._scoring import (
    _score_title,
    _score_steps,
    _score_expected_result,
    _score_precondition,
)


def _grade_to_quality_status(grade: str) -> str:
    """将评分等级(A/B/C/D)映射到4档质量状态。

    A -> passed, B -> warning, C -> pending_review, D -> rejected
    """
    mapping = {"A": "passed", "B": "warning", "C": "pending_review", "D": "rejected"}
    return mapping.get(grade, "pending_review")


class QualityGate(PipelineStep):
    name: ClassVar[str] = "quality_gate"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases"]
    produces: ClassVar[List[str]] = ["quality_scores"]

    def should_run(self, ctx: PipelineContext) -> bool:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        """缓存键必须包含所有影响评分结果的上下文字段。

        评分依赖：
            - generated_cases 中的 case 标题集合（已包含）
            - raw_signals（has_prd/has_ui/has_testpoints/is_old_project）
            - inferred_business_summary（confidence 影响分数）
            - aligned_testpoints（conflict_count 影响惩罚）
            - iteration_id（_check_user_confirmed 查库影响 confirmed 分数）

        若仅用 titles 作为键，当上游 signals/inferred/aligned 变化但标题集合
        不变时会命中陈旧评分，导致评分与上下文脱节。
        """
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return ""
        case_titles = []
        for entry in cases.get("generated_cases", []):
            if entry.get("status") == "success":
                for cd in entry.get("case_data", []):
                    case_titles.append(cd.get("title", ""))

        signals = ctx.get_artifact("raw_signals") or {}
        inferred = ctx.get_artifact("inferred_business_summary") or {}
        aligned = ctx.get_artifact("aligned_testpoints") or {}

        # 将 dict 序列化为稳定字符串后参与哈希，避免 dict 顺序差异
        signals_str = json.dumps(signals, ensure_ascii=False, sort_keys=True, default=str)
        inferred_str = json.dumps(inferred, ensure_ascii=False, sort_keys=True, default=str)
        aligned_str = json.dumps(aligned, ensure_ascii=False, sort_keys=True, default=str)

        raw = (
            f"{self.name}:{self.version}:titles={sorted(case_titles)}"
            f":signals={signals_str}:inferred={inferred_str}"
            f":aligned={aligned_str}:iteration_id={ctx.iteration_id}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        cases_artifact = ctx.get_artifact("generated_cases")
        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        signals = ctx.get_artifact("raw_signals") or {}
        inferred = ctx.get_artifact("inferred_business_summary") or {}
        aligned = ctx.get_artifact("aligned_testpoints") or {}

        analyzer = None
        try:
            from app.services.case_quality import CaseQualityAnalyzer
            if ctx.db is not None:
                analyzer = CaseQualityAnalyzer(ctx.db)
        except Exception as e:
            logger.warning("CaseQualityAnalyzer 初始化失败，降级到自研评分: {}", e)

        generated_cases = cases_artifact.get("generated_cases", [])
        scores = []
        total_score = 0.0
        graded_count = 0
        _score_idx = 0

        # 循环前查一次用户确认状态：iteration_id 在同一次 Pipeline 运行中不变，
        # 避免在评分循环内对每条用例重复查询 IterationInput 表（N+1）
        user_confirmed = _check_user_confirmed(ctx.db, ctx.iteration_id)

        tp_coverage_adj: Dict[Any, float] = {}
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            tp = entry.get("test_point") or _build_tp_from_task(entry.get("task"))
            tp_id = tp.get("id") if tp else None
            coverage_gap = entry.get("coverage_gap", [])
            if coverage_gap:
                tp_coverage_adj[tp_id] = -8.0 * len(coverage_gap)
            else:
                tp_coverage_adj[tp_id] = 5.0

        for entry in generated_cases:
            if entry.get("status") != "success":
                continue

            case_data_list = entry.get("case_data", [])
            tp = entry.get("test_point") or _build_tp_from_task(entry.get("task"))
            tp_id = tp.get("id") if tp else None
            coverage_adj = tp_coverage_adj.get(tp_id, 0.0)

            for case_data in case_data_list:
                if analyzer is not None:
                    try:
                        score, grade, breakdown = _compute_analyzer_score(analyzer, case_data)
                    except Exception as e:
                        logger.warning("CaseQualityAnalyzer 分析失败，降级到自研评分: {}", e)
                        score, grade, breakdown = _compute_prior_score(
                            case_data, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                            user_confirmed=user_confirmed,
                        )
                else:
                    score, grade, breakdown = _compute_prior_score(
                        case_data, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                        user_confirmed=user_confirmed,
                    )

                if coverage_adj != 0.0 and case_data_list:
                    per_case_adj = round(coverage_adj / len(case_data_list), 2)
                    score = max(0.0, min(100.0, round(score + per_case_adj, 2)))
                    breakdown["coverage_adjustment"] = per_case_adj
                    grade = _score_to_grade(score)

                scores.append({
                    "_score_idx": _score_idx,
                    "test_point_id": tp_id,
                    "case_title": case_data.get("title", ""),
                    "score": score,
                    "grade": grade,
                    "quality_status": _grade_to_quality_status(grade),
                    "breakdown": breakdown,
                    "lifecycle_status": case_data.get("lifecycle_status", "draft"),
                })
                total_score += score
                graded_count += 1

                case_data["prior_quality_score"] = score
                case_data["prior_quality_grade"] = grade
                if grade == "D":
                    case_data["lifecycle_status"] = "pending_review"
                    case_data["_d_score_idx"] = _score_idx

                _score_idx += 1

        d_grade_entries = _collect_d_grade_cases(generated_cases)
        if d_grade_entries:
            logger.info("R5: 发现 {} 条D级用例，尝试重生成", len(d_grade_entries))
            _regenerate_d_cases(ctx, d_grade_entries, signals, inferred, aligned, scores, analyzer)

        for entry in generated_cases:
            for c in entry.get("case_data", []):
                c.pop("_d_score_idx", None)

        total_score = sum(s["score"] for s in scores)
        graded_count = len(scores)
        avg_score = total_score / graded_count if graded_count > 0 else 0.0
        avg_grade = _score_to_grade(avg_score)

        clean_scores = []
        for s in scores:
            clean_scores.append({k: v for k, v in s.items() if not k.startswith("_")})

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": cases_artifact.get("project_id"),
            "scores": clean_scores,
            "total_graded": graded_count,
            "average_score": round(avg_score, 2),
            "average_grade": avg_grade,
            "needs_review_count": len([s for s in scores if s["grade"] == "D"]),
        }

        payload["module_coverage"] = _compute_module_coverage(generated_cases)
        payload["ui_element_coverage"] = _compute_ui_element_coverage(signals, cases_artifact)

        confidence = min(avg_score / 100.0, 1.0)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="quality_scores",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "avg_score": avg_score,
                "avg_grade": avg_grade,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "scores" in payload and "average_score" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        cases_artifact = ctx.get_artifact("generated_cases")
        generated_cases = cases_artifact.get("generated_cases", []) if cases_artifact else []
        scores = []
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            for case_data in entry.get("case_data", []):
                scores.append({
                    "test_point_id": (entry.get("test_point") or {}).get("id"),
                    "case_title": case_data.get("title", ""),
                    "score": 50.0,
                    "grade": "C",
                    "quality_status": "pending_review",
                    "breakdown": {"fallback": True},
                    "lifecycle_status": "pending_review",
                })

        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "scores": scores,
                "total_graded": len(scores),
                "average_score": 50.0,
                "average_grade": "C",
                "needs_review_count": len(scores),
            },
            artifact_kind="quality_scores",
            artifact_confidence=0.3,
            degraded=True,
        )


__all__ = [
    "QualityGate",
    "_compute_prior_score",
    "_compute_analyzer_score",
    "_score_to_grade",
    "_grade_to_quality_status",
    "_score_title",
    "_score_steps",
    "_score_expected_result",
    "_score_precondition",
    "_build_tp_from_task",
    "_classify_case_type_local",
    "_collect_d_grade_cases",
    "_regenerate_d_cases",
    "_compute_module_coverage",
    "_compute_ui_element_coverage",
]
