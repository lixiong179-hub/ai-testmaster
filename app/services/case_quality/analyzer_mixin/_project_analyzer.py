from typing import Dict, Any, List, Set
from datetime import datetime, timedelta
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.test_result import TestResult
from app.models.element_locator import ElementLocator
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.utils.db_time import utcnow
from app.services.case_quality.coverage_mixin import (
    _DEFAULT_TEST_POINT_PRIORITY_WEIGHT,
    _TEST_POINT_PRIORITY_WEIGHTS,
)
from app.services.case_quality.models import QualityReport


class _ProjectAnalyzerMixin:

    async def analyze_project_quality(self, project_id: int) -> Dict[str, Any]:
        cases: List[TestCase] = self.db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted.is_(False),
        ).all()

        if not cases:
            return {
                "project_id": project_id,
                "total_cases": 0,
                "average_score": 0,
                "quality_distribution": {},
                "top_issues": [],
                "reports": [],
            }

        case_ids: List[int] = [c.id for c in cases]

        all_steps: List[TestStep] = self.db.query(TestStep).filter(
            TestStep.test_case_id.in_(case_ids)
        ).order_by(TestStep.step_number).all()

        steps_map: Dict[int, List[TestStep]] = {cid: [] for cid in case_ids}
        for step in all_steps:
            steps_map[step.test_case_id].append(step)

        all_precondition_steps: List[TestCasePreconditionStep] = (
            self.db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id.in_(case_ids)
            ).order_by(TestCasePreconditionStep.step_number).all()
        )

        precondition_map: Dict[int, List[TestCasePreconditionStep]] = {
            cid: [] for cid in case_ids
        }
        for ps in all_precondition_steps:
            precondition_map[ps.test_case_id].append(ps)

        case_text_map: Dict[int, str] = {}
        for cid, case_steps in steps_map.items():
            actions = [s.action.strip().lower() for s in case_steps]
            case_text_map[cid] = " ".join(actions)

        all_step_ids: List[int] = [s.id for s in all_steps]
        all_locators: List[ElementLocator] = (
            self.db.query(ElementLocator).filter(
                ElementLocator.step_id.in_(all_step_ids)
            ).all() if all_step_ids else []
        )
        locators_by_step: Dict[int, List[ElementLocator]] = {}
        for loc in all_locators:
            if loc.step_id is not None:
                locators_by_step.setdefault(loc.step_id, []).append(loc)

        project_meta = self._build_project_coverage_context(project_id)
        coverage_context: Dict[str, Any] = {
            "locators_by_step": locators_by_step,
            **project_meta,
        }

        case_reports: List[QualityReport] = []
        for case in cases:
            try:
                report = await self._analyze_case_quality_internal(
                    case=case,
                    steps=steps_map.get(case.id, []),
                    precondition_steps=precondition_map.get(case.id, []),
                    all_cases=cases,
                    case_text_map=case_text_map,
                    coverage_context=coverage_context,
                )
                case_reports.append(report)
            except Exception as e:
                logger.error(f"分析用例失败 {case.id}: {e}")

        total_cases: int = len(case_reports)
        average_score: float = (
            sum(r.overall_score for r in case_reports) / total_cases
            if total_cases > 0 else 0
        )

        quality_distribution: Dict[str, int] = {
            "excellent": len([r for r in case_reports if r.overall_score >= 80]),
            "good": len([r for r in case_reports if 60 <= r.overall_score < 80]),
            "fair": len([r for r in case_reports if 40 <= r.overall_score < 60]),
            "poor": len([r for r in case_reports if r.overall_score < 40]),
        }

        all_issues: List[Dict[str, Any]] = []
        for report in case_reports:
            for suggestion in report.suggestions:
                all_issues.append({
                    "case_id": report.case_id,
                    "case_name": report.case_name,
                    "suggestion": suggestion,
                })

        project_requirement = self._calc_project_requirement_coverage(
            cases=cases,
            project_test_point_priorities=project_meta.get(
                "project_test_point_priorities", {}
            ),
        )

        return {
            "project_id": project_id,
            "total_cases": total_cases,
            "average_score": round(average_score, 1),
            "project_requirement_coverage": round(project_requirement["coverage_rate"], 4),
            "project_requirement_details": project_requirement["details"],
            "quality_distribution": quality_distribution,
            "top_issues": all_issues[:10],
            "reports": case_reports,
        }

    def _build_project_coverage_context(self, project_id: int) -> Dict[str, Any]:
        point_priorities: Dict[int, int] = {
            pid: priority for pid, priority in self.db.query(
                TestPoint.id, TestPoint.priority
            ).filter(
                TestPoint.project_id == project_id
            ).all()
        }

        ui_labels: Set[str] = set()
        spec_rows = self.db.query(UIPrototypeScreen.ui_spec).filter(
            UIPrototypeScreen.project_id == project_id
        ).all()
        for (spec,) in spec_rows:
            ui_labels.update(self._extract_ui_labels_from_spec(spec or {}))

        return {
            "project_test_point_priorities": point_priorities,
            "project_ui_labels": ui_labels,
        }

    @staticmethod
    def _calc_project_requirement_coverage(
        cases: List[TestCase],
        project_test_point_priorities: Dict[int, int],
    ) -> Dict[str, Any]:
        total_points = len(project_test_point_priorities)
        if total_points == 0:
            return {
                "coverage_rate": 0.0,
                "details": {
                    "available": False,
                    "covered_test_point_count": 0,
                    "project_total_test_points": 0,
                    "covered_weight_sum": 0.0,
                    "project_weight_sum": 0.0,
                    "covered_test_point_ids": [],
                    "scoring_mode": "priority_weighted_project_unique_points",
                },
            }

        covered_ids: Set[int] = {
            case.test_point_id
            for case in cases
            if getattr(case, "test_point_id", None) in project_test_point_priorities
        }

        def point_weight(priority: int) -> float:
            return _TEST_POINT_PRIORITY_WEIGHTS.get(
                priority, _DEFAULT_TEST_POINT_PRIORITY_WEIGHT
            )

        project_weight_sum = sum(
            point_weight(priority)
            for priority in project_test_point_priorities.values()
        )
        covered_weight_sum = sum(
            point_weight(project_test_point_priorities[tp_id])
            for tp_id in covered_ids
        )
        coverage_rate = (
            covered_weight_sum / project_weight_sum if project_weight_sum > 0 else 0.0
        )

        return {
            "coverage_rate": coverage_rate,
            "details": {
                "available": True,
                "covered_test_point_count": len(covered_ids),
                "project_total_test_points": total_points,
                "covered_weight_sum": round(covered_weight_sum, 4),
                "project_weight_sum": round(project_weight_sum, 4),
                "covered_test_point_ids": sorted(covered_ids),
                "scoring_mode": "priority_weighted_project_unique_points",
            },
        }

    _UI_SPEC_MAX_DEPTH = 20

    @staticmethod
    def _extract_ui_labels_from_spec(spec: Any) -> Set[str]:
        labels: Set[str] = set()
        candidate_keys = ("name", "label", "text", "description", "target")
        max_depth = _ProjectAnalyzerMixin._UI_SPEC_MAX_DEPTH

        def walk(node: Any, depth: int) -> None:
            if depth > max_depth:
                logger.warning(
                    f"_extract_ui_labels_from_spec: 递归深度超过 {max_depth}，提前终止"
                )
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in candidate_keys and isinstance(v, str):
                        cleaned = v.strip().lower()
                        if cleaned:
                            labels.add(cleaned)
                    walk(v, depth + 1)
            elif isinstance(node, list):
                for item in node:
                    walk(item, depth + 1)

        walk(spec, 0)
        return labels

    async def get_quality_trend(self, project_id: int, days: int = 30) -> List[Dict[str, Any]]:
        from_date = utcnow() - timedelta(days=days)

        cases: List[TestCase] = self.db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted.is_(False),
        ).all()

        if not cases:
            return []

        case_ids: List[int] = [c.id for c in cases]

        results: List[TestResult] = self.db.query(TestResult).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= from_date
        ).order_by(TestResult.exec_time).all()

        results_map: Dict[int, List[TestResult]] = {}
        for result in results:
            results_map.setdefault(result.case_id, []).append(result)

        case_title_map: Dict[int, str] = {c.id: c.title for c in cases}

        trend: List[Dict[str, Any]] = []
        for case_id, case_results in results_map.items():
            for result in case_results:
                trend.append({
                    "case_id": case_id,
                    "case_name": case_title_map.get(case_id, ""),
                    "date": result.exec_time.isoformat() if result.exec_time else None,
                    "status": result.exec_status,
                    "execution_time": getattr(result, 'execution_time', None),
                })

        return trend
