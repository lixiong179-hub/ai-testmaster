"""用例质量分析主入口Mixin - 提供analyze_case_quality等高层API。

性能优化（T15）：
    analyze_project_quality 采用批量预取 + 项目级嵌入向量缓存，
    将 O(N²) 数据库查询降至 O(1) 批量查询 + O(N) 内存计算。
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.test_result import TestResult
from app.models.element_locator import ElementLocator
from app.services.case_quality.models import QualityReport


class AnalyzerMixin:
    """用例质量分析主入口，整合各维度评估生成完整质量报告。"""

    async def analyze_case_quality(self, case_id: int) -> QualityReport:
        """分析单个用例质量，返回完整质量报告。

        Args:
            case_id: 测试用例ID。

        Returns:
            QualityReport: 完整质量报告。

        Raises:
            ValueError: 测试用例不存在时抛出。
        """
        test_case = self.db.query(TestCase).filter(TestCase.id == case_id).first()
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
            TestCase.id != case_id
        ).all()

        complexity = self._analyze_complexity(steps, precondition_steps)
        redundancy = self._analyze_redundancy(test_case, steps, all_cases)
        coverage = self._analyze_coverage(steps)
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

    async def analyze_project_quality(self, project_id: int) -> Dict[str, Any]:
        """分析整个项目的用例质量，批量预取数据消除N²查询。

        优化策略：
            1. 批量预取全部用例、步骤、前置步骤、定位器（4次查询）
            2. 项目级缓存嵌入向量（步骤文本），冗余度检测直接内存比对
            3. 逐用例分析时零额外数据库查询

        Args:
            project_id: 项目ID。

        Returns:
            Dict[str, Any]: 项目质量汇总，包含分布、问题列表和各用例报告。
        """
        # ---- 批量预取：1次查询获取全部用例 ----
        cases: List[TestCase] = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
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

        # ---- 批量预取：1次查询获取全部步骤 ----
        all_steps: List[TestStep] = self.db.query(TestStep).filter(
            TestStep.test_case_id.in_(case_ids)
        ).order_by(TestStep.step_number).all()

        steps_map: Dict[int, List[TestStep]] = {cid: [] for cid in case_ids}
        for step in all_steps:
            steps_map[step.test_case_id].append(step)

        # ---- 批量预取：1次查询获取全部前置步骤 ----
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

        # ---- 项目级缓存：一次计算嵌入向量（步骤文本）用于冗余度检测 ----
        case_text_map: Dict[int, str] = {}
        for cid, case_steps in steps_map.items():
            actions = [s.action.strip().lower() for s in case_steps]
            case_text_map[cid] = " ".join(actions)

        # ---- 批量预取：1次查询获取全部定位器 ----
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

        coverage_context: Dict[str, Any] = {
            "locators_by_step": locators_by_step,
        }

        # ---- 逐用例分析（使用预取数据，零额外查询） ----
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

        return {
            "project_id": project_id,
            "total_cases": total_cases,
            "average_score": round(average_score, 1),
            "quality_distribution": quality_distribution,
            "top_issues": all_issues[:10],
            "reports": case_reports,
        }

    async def _analyze_case_quality_internal(
        self,
        case: TestCase,
        steps: List[TestStep],
        precondition_steps: List[TestCasePreconditionStep],
        all_cases: List[TestCase],
        case_text_map: Dict[int, str],
        coverage_context: Dict[str, Any],
    ) -> QualityReport:
        """使用预取数据分析单个用例质量，不执行额外数据库查询。

        Args:
            case: 测试用例对象。
            steps: 该用例的步骤列表（已预取）。
            precondition_steps: 该用例的前置步骤列表（已预取）。
            all_cases: 项目全部用例列表（已预取）。
            case_text_map: 用例ID到步骤文本的映射（嵌入向量缓存）。
            coverage_context: 覆盖率预取数据上下文。

        Returns:
            QualityReport: 完整质量报告。
        """
        logger.info(f"开始分析用例质量: {case.title} (ID: {case.id})")

        complexity = self._analyze_complexity(steps, precondition_steps)
        redundancy = self._analyze_redundancy(
            case, steps, all_cases, case_text_map=case_text_map
        )
        coverage = self._analyze_coverage(
            steps, coverage_context=coverage_context,
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

    async def get_quality_trend(self, project_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """获取项目用例质量趋势（基于执行历史），批量预取消除N+1查询。

        Args:
            project_id: 项目ID。
            days: 回溯天数，默认30。

        Returns:
            List[Dict[str, Any]]: 趋势数据列表。
        """
        from_date = datetime.now() - timedelta(days=days)

        cases: List[TestCase] = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()

        if not cases:
            return []

        case_ids: List[int] = [c.id for c in cases]

        # 批量预取：1次查询获取全部执行结果
        results: List[TestResult] = self.db.query(TestResult).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= from_date
        ).order_by(TestResult.exec_time).all()

        # 构建用例ID到执行结果的映射
        results_map: Dict[int, List[TestResult]] = {}
        for result in results:
            results_map.setdefault(result.case_id, []).append(result)

        # 构建用例ID到标题的映射，避免循环内属性访问
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


CaseQualityAnalyzerMixin = AnalyzerMixin
