"""Test Case Generation - 历史用例信任度与上下文评分 Mixin

从 base_mixin.py 拆分，包含：
    - enrich_context_with_trust_and_scoring: 历史用例注入 + 信任度过滤 + 完整性评分 + AB 指标
    - _compute_completeness_score: 上下文完整性评分（测试点/需求/UI/流程/历史 5 维度）

拆分理由：base_mixin.py 单文件 694 行超 350 行规范（项目规则第三章）。
"""
from typing import Any, Dict, List

from app.models.project import Project
from app.models.test_case import TestCase
from app.services.test_case_generation._base_helpers import _has_flow_intent


class TestCaseGenerationHistoryScoringMixin:
    """测试用例生成服务 - 历史信任度与评分 Mixin"""

    __test__ = False

    def enrich_context_with_trust_and_scoring(
        self,
        context: Dict[str, Any],
        project_id: int,
        history_case_ids: list[int] | None = None,
        history_limit: int = 10,
    ) -> None:
        """注入历史用例并基于信任度过滤，计算上下文完整性评分"""
        from app.api.v1.endpoints.test_case_ai_generate._context import (
            _extract_terms, _score_terms, _assess_history_trust, _summarize_history_case,
        )

        current_requirement_ids: set[int] = set()
        current_ui_screen_ids: set[int] = set()
        for tp in context.get("test_points", []):
            if isinstance(tp, dict) and tp.get("requirement_id"):
                current_requirement_ids.add(tp["requirement_id"])
        for ui_ref in context.get("evidence_refs", {}).get("ui_screens", []):
            if isinstance(ui_ref, dict) and ui_ref.get("id"):
                current_ui_screen_ids.add(ui_ref["id"])

        if history_case_ids is not None and len(history_case_ids) == 0:
            cases = []
            similarity_by_case_id = {}
        elif history_case_ids is not None and len(history_case_ids) > 0:
            cases = self.db.query(TestCase).filter(
                TestCase.id.in_(history_case_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.notin_(['archived', 'deprecated']),
            ).all()
            similarity_by_case_id = {}
        else:
            search_terms = []
            for tp in context.get("test_points", []):
                if isinstance(tp, dict):
                    search_terms.append(f"{tp.get('module', '')} {tp.get('point', '')} {tp.get('function', '')}")
            query_terms = _extract_terms(*search_terms) if search_terms else set()
            all_cases = self.db.query(TestCase).filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.notin_(['archived', 'deprecated']),
            ).order_by(TestCase.id).all()
            if query_terms:
                scored_cases = []
                for case in all_cases:
                    score = _score_terms(
                        query_terms, case.module, case.title,
                        case.summary, case.expected_result, case.steps_json,
                    )
                    if score > 0:
                        scored_cases.append((score, case))
                scored_cases.sort(key=lambda item: (-item[0], item[1].id))
                max_score = scored_cases[0][0] if scored_cases else 0
                cases = [case for _, case in scored_cases[:history_limit]]
                similarity_by_case_id = {
                    case.id: (score / max_score if max_score else 0.0)
                    for score, case in scored_cases[:history_limit]
                }
                if not cases:
                    context.setdefault("warnings", []).append({
                        "code": "HISTORY_NO_SIMILAR_CASE",
                        "message": "未找到与当前测试点相似的历史用例，默认不注入历史参考",
                        "detail": {"limit": history_limit},
                    })
            else:
                cases = []
                similarity_by_case_id = {}
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_NO_QUERY_TEXT",
                    "message": "测试点文本为空，默认不注入历史用例",
                    "detail": {},
                })

        history_cases = []
        low_trust_filtered_count = 0
        for c in cases:
            trust_level, staleness_reason = _assess_history_trust(
                c, current_requirement_ids, current_ui_screen_ids, self.db,
            )
            if trust_level == "low":
                low_trust_filtered_count += 1
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_LOW_TRUST_FILTERED",
                    "message": f"历史用例「{c.title}」需求不匹配，已从生成上下文中剔除",
                    "detail": {"case_id": c.id, "case_no": c.case_no, "staleness_reason": staleness_reason},
                })
                continue
            if trust_level == "medium":
                low_trust_filtered_count += 1
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_POTENTIALLY_STALE",
                    "message": f"历史用例「{c.title}」可信度不足，已从生成上下文中剔除",
                    "detail": {"case_id": c.id, "case_no": c.case_no, "trust_level": trust_level, "staleness_reason": staleness_reason},
                })
                continue
            history_cases.append(_summarize_history_case(
                c,
                similarity_by_case_id.get(c.id),
                trust_level=trust_level,
                staleness_reason=staleness_reason,
            ))

        context["history_cases"] = history_cases
        context.setdefault("evidence_refs", {})["history_cases"] = [
            {
                "id": item["id"],
                "case_no": item.get("case_no"),
                "design_tag": item.get("design_tag"),
                "similarity": item.get("similarity"),
                "trust_level": item.get("trust_level", "high"),
                "staleness_reason": item.get("staleness_reason", ""),
            }
            for item in history_cases
        ]
        context.setdefault("context_stats", {})["history_cases_used"] = len(history_cases)
        if low_trust_filtered_count > 0:
            context["context_stats"]["history_low_trust_filtered"] = low_trust_filtered_count

        completeness = self._compute_completeness_score(context=context, project_id=project_id)
        context["context_stats"]["completeness_score"] = completeness["score"]
        context["context_stats"]["missing_core_context"] = completeness["missing_core_context"]
        context["context_stats"]["low_confidence_reasons"] = completeness["low_confidence_reasons"]
        if completeness["score"] < 80:
            context.setdefault("warnings", []).append({
                "code": "CONTEXT_COMPLETENESS_LOW",
                "message": (
                    f"上下文完整性评分 {completeness['score']}，"
                    + ("建议人工复核" if completeness["score"] < 50 else "部分步骤可能需标记待确认")
                ),
                "detail": {"score": completeness["score"], "missing": completeness["missing_core_context"]},
            })
        context["evidence_refs"]["warnings"] = context.get("warnings", [])

        try:
            from app.db.database import PrimarySessionLocal
            from app.services.ab_test_service import ABTestService
            _ab_db = PrimarySessionLocal()
            try:
                _ab_service = ABTestService(_ab_db)
                _ab_service.record_metric(
                    experiment_id="context_precision_v1",
                    variant="treatment",
                    project_id=project_id,
                    metric_name="completeness_score",
                    metric_value=float(context["context_stats"].get("completeness_score", 0)),
                    detail={
                        "missing_core_context": context["context_stats"].get("missing_core_context", []),
                        "low_confidence_reasons": context["context_stats"].get("low_confidence_reasons", []),
                    },
                )
                _ab_db.commit()
            except Exception:
                _ab_db.rollback()
            finally:
                _ab_db.close()
        except Exception:
            pass

    def _compute_completeness_score(
        self,
        context: Dict[str, Any],
        project_id: int,
    ) -> Dict[str, Any]:
        """计算上下文完整性评分（测试点/需求/UI/流程/历史 5 维度加权）"""
        WEIGHT_TEST_POINT = 20
        WEIGHT_REQUIREMENT = 35
        WEIGHT_UI = 25
        WEIGHT_FLOW = 10
        WEIGHT_HISTORY = 10

        missing_core_context: List[str] = []
        low_confidence_reasons: List[str] = []
        score = 0

        test_points = context.get("test_points", [])
        has_test_point = bool(test_points) and all(
            tp.get("point") and tp.get("module") for tp in test_points if isinstance(tp, dict)
        )
        if has_test_point:
            score += WEIGHT_TEST_POINT
        else:
            missing_core_context.append("test_point")

        has_requirement = bool(context.get("requirement_content", "").strip())
        if has_requirement:
            score += WEIGHT_REQUIREMENT
        else:
            missing_core_context.append("requirement")
            low_confidence_reasons.append("REQUIREMENT_NOT_FOUND")

        ui_specs = context.get("ui_specs", [])
        ui_descriptions = context.get("ui_descriptions", [])
        has_ui = bool(ui_specs) or any(
            d.get("parse_status") == "completed" for d in ui_descriptions if isinstance(d, dict)
        )
        project = self.db.query(Project).filter(Project.id == project_id).first() if project_id else None
        is_ui_project = project and (project.project_type or "web") in ("web", "app")

        if has_ui:
            score += WEIGHT_UI
        else:
            if is_ui_project:
                missing_core_context.append("ui")
                low_confidence_reasons.append("UI_NO_MATCH")
            else:
                score += int(WEIGHT_UI * WEIGHT_REQUIREMENT / (WEIGHT_REQUIREMENT + WEIGHT_TEST_POINT))

        has_flow = any(
            _has_flow_intent(f"{tp.get('module', '')} {tp.get('point', '')}")
            for tp in test_points if isinstance(tp, dict)
        )
        if has_flow and has_ui:
            matched_screen_ids = {s.get("screen_id") or s.get("id") for s in ui_descriptions if isinstance(s, dict)}
            has_navigation = any(
                isinstance(s.get("navigation_flow") or s.get("related_screens"), (dict, list))
                for s in ui_specs if isinstance(s, dict)
            )
            if has_navigation or len(matched_screen_ids) > 1:
                score += WEIGHT_FLOW
            else:
                score += WEIGHT_FLOW // 2
                low_confidence_reasons.append("UI_NO_NAVIGATION")
        elif not has_flow:
            score += WEIGHT_FLOW
        else:
            score += WEIGHT_FLOW // 4

        history_cases_used = context.get("context_stats", {}).get("history_cases_used", 0)
        if history_cases_used > 0:
            score += WEIGHT_HISTORY
        elif not missing_core_context:
            score += WEIGHT_HISTORY

        return {
            "score": min(100, score),
            "missing_core_context": missing_core_context,
            "low_confidence_reasons": low_confidence_reasons,
        }
