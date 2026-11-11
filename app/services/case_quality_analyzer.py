# [R4-5 冻结 2026-11-10] 生产代码零引用（仅测试引用），保留备用；接线或删除前请先在《架构优化执行计划清单》登记。
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
