# [R4-5 冻结 2026-11-10] 生产代码零引用（仅测试引用），保留备用；接线或删除前请先在《架构优化执行计划清单》登记。
"""成本统计模型 - 定义成本统计的数据结构和枚举。"""

from typing import Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CostStatistics:
    total_steps: int
    ai_vision_calls: int
    cache_hits: int
    css_selector_used: int
    xpath_used: int
    estimated_cost: float
    actual_cost: float
    cost_savings: float
    savings_rate: float
    cache_hit_rate: float
    ai_dependency_rate: float
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CostReport:
    report_id: str
    project_id: int
    start_date: datetime
    end_date: datetime
    overall_statistics: CostStatistics
    case_statistics: list[dict[str, Any]]
    daily_statistics: list[dict[str, Any]]
    optimization_suggestions: list[dict[str, Any]]
    trend_data: list[dict[str, Any]]
    generated_at: datetime = field(default_factory=datetime.now)


def _build_empty_statistics() -> CostStatistics:
    return CostStatistics(
        total_steps=0,
        ai_vision_calls=0,
        cache_hits=0,
        css_selector_used=0,
        xpath_used=0,
        estimated_cost=0,
        actual_cost=0,
        cost_savings=0,
        savings_rate=0,
        cache_hit_rate=0,
        ai_dependency_rate=0,
    )
