"""用例质量分析主入口Mixin - 提供analyze_case_quality等高层API。

性能优化（T15）：
    analyze_project_quality 采用批量预取 + 项目级嵌入向量缓存，
    将 O(N²) 数据库查询降至 O(1) 批量查询 + O(N) 内存计算。
"""
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from loguru import logger

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.test_result import TestResult
from app.models.element_locator import ElementLocator
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.services.case_quality.coverage_mixin import (
    _DEFAULT_TEST_POINT_PRIORITY_WEIGHT,
    _TEST_POINT_PRIORITY_WEIGHTS,
)
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

        # T1: 预取项目级需求/UI 元数据供三维覆盖率计算
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

        # T1: 预取项目级需求/UI 元数据（仅 1 次查询）
        project_meta = self._build_project_coverage_context(project_id)
        coverage_context: Dict[str, Any] = {
            "locators_by_step": locators_by_step,
            **project_meta,
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

    def _build_project_coverage_context(self, project_id: int) -> Dict[str, Any]:
        """预取项目级需求/UI 元数据，供三维覆盖率计算使用。

        返回两个关键字段：
            - project_test_point_priorities: Dict[int, int] 项目下测试点 ID -> priority
            - project_ui_labels: Set[str]        项目下全部 UI 元素标签（小写）

        两者均为可选性资源：项目未导入需求或未上传 UI 原型时集合为空，
        对应维度在 coverage_mixin 中会被标为不可用。
        """
        # 测试点优先级映射（只取 id/priority 列，避免加载整行）
        point_priorities: Dict[int, int] = {
            pid: priority for pid, priority in self.db.query(
                TestPoint.id, TestPoint.priority
            ).filter(
                TestPoint.project_id == project_id
            ).all()
        }

        # UI 元素标签集：只查 ui_spec JSON 列，避免加载整行（JSON 可能较大）
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
        """计算项目级需求覆盖率。

        口径：项目中“至少被一个用例绑定”的测试点，按优先级权重去重累计，
        再除以项目全部测试点权重总和。

        这与单用例 `requirement_coverage_rate` 不同：
            - 单用例：衡量该用例的需求追踪绑定质量
            - 项目级：衡量项目全部测试点是否被用例集合覆盖
        """
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

    # 递归深度上限：防止恶意/损坏的 ui_spec 出现循环引用或超深嵌套时 RecursionError 冒泡到端点。
    # 20 层足以覆盖常见 UI 原型结构（页面→容器→组件→子组件…）。
    _UI_SPEC_MAX_DEPTH = 20

    @staticmethod
    def _extract_ui_labels_from_spec(spec: Any) -> Set[str]:
        """从 ui_spec JSON 中提取元素标签。

        兼容多种常见结构：
            - {"elements": [{"name": "登录按钮"}, {"label": "..."}]}
            - {"components": [...]}
            - 嵌套列表。

        提取后统一转为小写去除空格，用于与 step.target_element 进行包含匹配。
        超过递归深度上限时会警告并提前结束，但不抛出异常。
        """
        labels: Set[str] = set()
        candidate_keys = ("name", "label", "text", "description", "target")
        max_depth = AnalyzerMixin._UI_SPEC_MAX_DEPTH

        def walk(node: Any, depth: int) -> None:
            if depth > max_depth:
                logger.warning(
                    f"_extract_ui_labels_from_spec: 递归深度超过 {max_depth}，提前终止"
                )
                return
            if isinstance(node, dict):
                # 一次遍历 items：candidate_keys 提取后继续递归 value，避免重复扫描
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
