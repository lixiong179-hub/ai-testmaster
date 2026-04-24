"""成本统计数据模型定义。"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CostStatistics:
    """成本统计数据"""
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
    """成本报表"""
    report_id: str
    project_id: int
    start_date: datetime
    end_date: datetime
    overall_statistics: CostStatistics
    case_statistics: List[Dict[str, Any]]
    daily_statistics: List[Dict[str, Any]]
    optimization_suggestions: List[Dict[str, Any]]
    trend_data: List[Dict[str, Any]]
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CostStatisticsRequest:
    """兼容旧测试导出的统计请求模型。"""

    project_id: int
    start_date: datetime
    end_date: datetime
    group_by: str = "day"


@dataclass
class CostReportData:
    """兼容旧测试导出的聚合成本报告模型。"""

    project_id: int
    total_cost: float = 0.0
    total_tokens: int = 0
    avg_cost_per_request: float = 0.0
    daily_costs: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def avg_cost_per_requests(self) -> float:
        return self.avg_cost_per_request
