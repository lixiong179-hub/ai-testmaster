"""成本报表Mixin - 报表生成与优化建议。"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from app.services.cost_statistics.models import CostStatistics, CostReport
from app.utils.db_time import utcnow


class CostStatisticsReportMixin:
    """成本报表生成与优化建议。"""

    COST_PER_AI_VISION_CALL = 0.1
    AI_DEPENDENCY_THRESHOLD = 50.0
    BATCH_RECOGNITION_MIN_STEPS = 10
    CACHE_HIT_RATE_THRESHOLD = 70.0
    LOCATOR_SAVINGS_RATE = 0.8
    BATCH_SAVINGS_RATE = 0.3
    CACHE_SAVINGS_RATE = 0.2

    def generate_cost_report(
        self,
        project_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> CostReport:
        if not end_date:
            end_date = utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        overall_stats = self.get_project_cost_statistics(project_id)
        case_stats = self._get_case_cost_details(project_id)
        daily_stats = self._get_daily_cost_statistics(project_id, start_date, end_date)
        suggestions = self._generate_cost_optimization_suggestions(project_id, overall_stats)
        trend_data = self._get_cost_trend(project_id, start_date, end_date)

        report = CostReport(
            report_id=f"COST-{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
            overall_statistics=overall_stats,
            case_statistics=case_stats,
            daily_statistics=daily_stats,
            optimization_suggestions=suggestions,
            trend_data=trend_data
        )
        logger.info(f"成本报表生成完成: {report.report_id}")
        return report

    def _generate_cost_optimization_suggestions(
        self, project_id: int, overall_stats: CostStatistics
    ) -> List[Dict[str, Any]]:
        suggestions = []

        if overall_stats.ai_dependency_rate > self.AI_DEPENDENCY_THRESHOLD:
            potential_savings = (
                overall_stats.ai_vision_calls * self.COST_PER_AI_VISION_CALL * self.LOCATOR_SAVINGS_RATE
            )
            suggestions.append({
                "type": "补充元素定位",
                "description": f"AI依赖率较高({overall_stats.ai_dependency_rate}%)，建议为更多步骤补充元素定位信息",
                "potential_savings": round(potential_savings, 2),
                "priority": "high",
                "impact": "可显著降低AI视觉成本"
            })

        if overall_stats.total_steps >= self.BATCH_RECOGNITION_MIN_STEPS:
            batch_savings = (
                overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.BATCH_SAVINGS_RATE
            )
            suggestions.append({
                "type": "启用批量识别",
                "description": "用例步骤较多，建议使用批量元素识别功能",
                "potential_savings": round(batch_savings, 2),
                "priority": "medium",
                "impact": "减少AI调用次数"
            })

        if overall_stats.cache_hit_rate < self.CACHE_HIT_RATE_THRESHOLD:
            cache_savings = (
                overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.CACHE_SAVINGS_RATE
            )
            suggestions.append({
                "type": "优化缓存策略",
                "description": f"缓存命中率较低({overall_stats.cache_hit_rate}%)，建议优化定位缓存策略",
                "potential_savings": round(cache_savings, 2),
                "priority": "medium",
                "impact": "提升缓存利用率"
            })

        return suggestions
