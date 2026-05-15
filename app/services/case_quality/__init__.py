"""用例质量子包 - 通过Mixin组合模式实现测试用例质量评估能力。

本子包是用例质量评估体系的核心实现，CaseQualityAnalyzer通过多继承
组合各功能Mixin，实现复杂度评估、覆盖度评估、冗余度检测和改进建议。

核心类:
    - CaseQualityAnalyzer: 用例质量分析器主类

Mixin组合:
    - AnalyzerMixin: 质量分析主入口（analyze_case_quality等）
    - SuggestionMixin: 改进建议生成
    - RedundancyMixin: 冗余度检测
    - CoverageMixin: 覆盖度评估
    - ComplexityMixin: 复杂度评估

评估维度:
    - 复杂度: 步骤数量、条件分支、数据依赖
    - 覆盖度: 功能覆盖、场景覆盖、边界覆盖
    - 冗余度: 步骤重复、逻辑重复、数据重复
    - 建议: 基于评估结果的改进建议
"""
from types import SimpleNamespace
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
)
from app.services.case_quality.complexity_mixin import ComplexityMixin
from app.services.case_quality.coverage_mixin import CoverageMixin
from app.services.case_quality.redundancy_mixin import RedundancyMixin
from app.services.case_quality.suggestion_mixin import SuggestionMixin
from app.services.case_quality.analyzer_mixin import AnalyzerMixin


class CaseQualityAnalyzer(
    AnalyzerMixin,
    SuggestionMixin,
    RedundancyMixin,
    CoverageMixin,
    ComplexityMixin,
):
    """用例质量分析器 - 组合复杂度/覆盖度/冗余度/建议四个评估维度。

    继承顺序（MRO）:
        AnalyzerMixin -> SuggestionMixin -> RedundancyMixin -> CoverageMixin -> ComplexityMixin

    使用场景:
        - 用例生成后自动评估质量
        - 用例质量报告生成
        - 用例优化建议
    """

    def __init__(self, db: Session):
        """初始化用例质量分析器。

        Args:
            db: 数据库会话。
        """
        self.db = db

    def analyze_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        steps_raw = case_data.get("steps", [])
        steps = []
        if isinstance(steps_raw, list):
            for i, s in enumerate(steps_raw):
                if isinstance(s, dict):
                    steps.append(SimpleNamespace(
                        id=i,
                        action=s.get("action", s.get("description", "")),
                        target_element=s.get("target_element", ""),
                        expected_result=s.get("expected_result", s.get("expected", "")),
                        step_number=i + 1,
                    ))
                elif isinstance(s, str):
                    steps.append(SimpleNamespace(
                        id=i,
                        action=s,
                        target_element="",
                        expected_result="",
                        step_number=i + 1,
                    ))
        elif isinstance(steps_raw, str) and steps_raw.strip():
            steps.append(SimpleNamespace(
                id=0,
                action=steps_raw,
                target_element="",
                expected_result="",
                step_number=1,
            ))

        precondition_steps = []
        precondition_raw = case_data.get("precondition", "")
        if precondition_raw:
            precondition_steps.append(SimpleNamespace(
                action=str(precondition_raw),
                step_number=1,
            ))

        complexity = self._analyze_complexity(steps, precondition_steps)

        fake_case = SimpleNamespace(
            id=-1,
            title=case_data.get("title", ""),
            project_id=-1,
            test_point_id=None,
        )
        redundancy = self._analyze_redundancy(fake_case, steps, all_cases=[])

        coverage = self._analyze_coverage(steps, coverage_context={}, case=None)

        suggestions = self._generate_optimization_suggestions(complexity, redundancy, coverage)

        return {
            "complexity_score": complexity.score,
            "coverage_score": coverage.score,
            "redundancy_score": redundancy.score,
            "suggestion_count": len(suggestions),
        }


__all__ = [
    'CaseQualityAnalyzer',
    'ComplexityScore',
    'RedundancyScore',
    'CoverageScore',
    'QualityReport',
    'ComplexityMixin',
    'CoverageMixin',
    'RedundancyMixin',
    'SuggestionMixin',
    'AnalyzerMixin',
]
