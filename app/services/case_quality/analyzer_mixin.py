"""用例质量分析主入口Mixin - 提供analyze_case_quality等高层API。"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.test_result import TestResult
from app.services.case_quality.models import QualityReport


class AnalyzerMixin:
    """用例质量分析主入口，整合各维度评估生成完整质量报告。"""

    async def analyze_case_quality(self, case_id: int) -> QualityReport:
        """分析单个用例质量，返回完整质量报告。"""
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
        """分析整个项目的用例质量。"""
        cases = self.db.query(TestCase).filter(
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

        case_reports = []
        for case in cases:
            try:
                report = await self.analyze_case_quality(case.id)
                case_reports.append(report)
            except Exception as e:
                logger.error(f"分析用例失败 {case.id}: {e}")

        total_cases = len(case_reports)
        average_score = (
            sum(r.overall_score for r in case_reports) / total_cases
            if total_cases > 0 else 0
        )

        quality_distribution = {
            "excellent": len([r for r in case_reports if r.overall_score >= 80]),
            "good": len([r for r in case_reports if 60 <= r.overall_score < 80]),
            "fair": len([r for r in case_reports if 40 <= r.overall_score < 60]),
            "poor": len([r for r in case_reports if r.overall_score < 40]),
        }

        all_issues = []
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

    async def get_quality_trend(self, project_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """获取项目用例质量趋势（基于执行历史）。"""
        from_date = datetime.now() - timedelta(days=days)

        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()

        trend = []
        for case in cases:
            results = self.db.query(TestResult).filter(
                TestResult.case_id == case.id,
                TestResult.exec_time >= from_date
            ).order_by(TestResult.exec_time).all()

            for result in results:
                trend.append({
                    "case_id": case.id,
                    "case_name": case.title,
                    "date": result.exec_time.isoformat() if result.exec_time else None,
                    "status": result.exec_status,
                    "execution_time": result.execution_time if hasattr(result, 'execution_time') else None,
                })

        return trend


CaseQualityAnalyzerMixin = AnalyzerMixin
