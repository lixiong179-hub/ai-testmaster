"""成本统计子包 - AI视觉调用成本统计与优化建议。

核心类:
    - CostStatisticsService: 成本统计服务主类

Mixin组合:
    - CostStatisticsQueryMixin: 用例/项目成本统计与趋势查询
    - CostStatisticsReportMixin: 成本报表生成与优化建议
"""
from sqlalchemy.orm import Session

from app.services.cost_statistics.models import CostStatistics, CostReport
from app.services.cost_statistics.query_mixin import CostStatisticsQueryMixin
from app.services.cost_statistics.report_mixin import CostStatisticsReportMixin


class CostStatisticsService(CostStatisticsQueryMixin, CostStatisticsReportMixin):
    """AI视觉成本统计服务。

    功能：
    1. 统计AI视觉调用次数和成本
    2. 分析缓存命中率
    3. 生成成本优化建议
    4. 提供成本趋势分析
    5. 生成成本报表
    """

    def __init__(self, db: Session):
        self.db = db


__all__ = [
    "CostStatisticsService",
    "CostStatistics",
    "CostReport",
]
