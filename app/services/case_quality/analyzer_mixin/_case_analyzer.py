from typing import Dict, Any, List
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.services.case_quality.models import QualityReport


class _CaseAnalyzerMixin:

    async def analyze_case_quality(self, case_id: int) -> QualityReport:
        test_case = self.db.query(TestCase).filter(TestCase.id == case_id, TestCase.is_deleted.is_(False)).first()
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")

        logger.info(f"开始分析用例质量: {test_case.title} (ID: {case_id})")

        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == case_id
        ).order_by(TestStep.step_number).all()

        precondition_steps = self.db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.test_case_id == case_id
        ).order_by(TestCasePreconditionStep.step_number).all()

        all_cases = self.db.query(TestCase).filter(
            TestCase.project_id == test_case.project_id,
            TestCase.id != case_id,
            TestCase.is_deleted.is_(False),
        ).all()

        coverage_context = self._build_project_coverage_context(test_case.project_id)

        complexity = self._analyze_complexity(steps, precondition_steps)
        redundancy = self._analyze_redundancy(test_case, steps, all_cases)
        coverage = self._analyze_coverage(steps, coverage_context=coverage_context, case=test_case)
        suggestions = self._generate_optimization_suggestions(complexity, redundancy, coverage)

        overall_score = self._calculate_overall_score(complexity, redundancy, coverage)

        if overall_score >= 80:
            overall_level = "excellent"
        elif overall_score >= 60:
            overall_level = "good"
        elif overall_score >= 40:
            overall_level = "fair"
        else:
            overall_level = "poor"

        report = QualityReport(
            case_id=case_id,
            case_name=test_case.title,
            overall_score=overall_score,
            overall_level=overall_level,
            complexity=complexity,
            redundancy=redundancy,
            coverage=coverage,
            suggestions=suggestions,
        )

        logger.info(f"用例质量分析完成: {test_case.title}, 综合评分: {overall_score:.1f}")
        return report

    async def _analyze_case_quality_internal(
        self,
        case: TestCase,
        steps: List[TestStep],
        precondition_steps: List[TestCasePreconditionStep],
        all_cases: List[TestCase],
        case_text_map: Dict[int, str],
        coverage_context: Dict[str, Any],
    ) -> QualityReport:
        logger.info(f"开始分析用例质量: {case.title} (ID: {case.id})")

        complexity = self._analyze_complexity(steps, precondition_steps)
        redundancy = self._analyze_redundancy(
            case, steps, all_cases, case_text_map=case_text_map
        )
        coverage = self._analyze_coverage(
            steps, coverage_context=coverage_context, case=case,
        )
        suggestions = self._generate_optimization_suggestions(complexity, redundancy, coverage)

        overall_score = self._calculate_overall_score(complexity, redundancy, coverage)

        if overall_score >= 80:
            overall_level = "excellent"
        elif overall_score >= 60:
            overall_level = "good"
        elif overall_score >= 40:
            overall_level = "fair"
        else:
            overall_level = "poor"

        report = QualityReport(
            case_id=case.id,
            case_name=case.title,
            overall_score=overall_score,
            overall_level=overall_level,
            complexity=complexity,
            redundancy=redundancy,
            coverage=coverage,
            suggestions=suggestions,
        )

        logger.info(f"用例质量分析完成: {case.title}, 综合评分: {overall_score:.1f}")
        return report
