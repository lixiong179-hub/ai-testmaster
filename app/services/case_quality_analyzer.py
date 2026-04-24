"""
用例质量分析服务 - 兼容代理模块

所有实现已迁移到 case_quality/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.case_quality import (
    CaseQualityAnalyzer,
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
)

__all__ = [
    "CaseQualityAnalyzer",
    "ComplexityScore",
    "RedundancyScore",
    "CoverageScore",
    "QualityReport",
]
