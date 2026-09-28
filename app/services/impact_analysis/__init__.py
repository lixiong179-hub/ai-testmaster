"""Test Impact Analysis 服务包（Phase 1 Task 4：智能调度 v1）

业务用途：分析代码变更识别受影响测试用例，仅运行必要用例，回归时间缩短 ≥50%。
设计原则：
1. 基于覆盖率数据冷启动，避免映射不准风险；
2. 模块化设计，覆盖率采集/变更分析/影响映射独立可测；
3. 与现有 Pipeline 执行解耦，通过调度器接口接入。

依赖：coverage.py（数据采集）、gitpython（变更分析）
"""
from app.services.impact_analysis.models import (
    CoverageEntry,
    CodeChange,
    ImpactResult,
    ImpactRange,
)
from app.services.impact_analysis.coverage_collector import CoverageCollector
from app.services.impact_analysis.change_analyzer import ChangeAnalyzer
from app.services.impact_analysis.impact_mapper import ImpactMapper
from app.services.impact_analysis.scheduler import ImpactScheduler, ImpactSchedulePlan
from app.services.impact_analysis.integration_service import TIAIntegrationService

__all__ = [
    "CoverageEntry",
    "CodeChange",
    "ImpactResult",
    "ImpactRange",
    "CoverageCollector",
    "ChangeAnalyzer",
    "ImpactMapper",
    "ImpactScheduler",
    "ImpactSchedulePlan",
    "TIAIntegrationService",
]
