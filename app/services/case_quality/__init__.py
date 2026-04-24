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
