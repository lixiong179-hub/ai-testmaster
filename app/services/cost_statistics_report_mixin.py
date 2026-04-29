"""成本报告Mixin - 生成成本统计报告和趋势分析。
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from loguru import logger
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.services.cost_statistics_models import CostStatistics, CostReport


class CostStatisticsReportMixin:
    AI_DEPENDENCY_THRESHOLD = 50.0
    BATCH_RECOGNITION_MIN_STEPS = 10
    CACHE_HIT_RATE_THRESHOLD = 70.0
    LOCATOR_SAVINGS_RATE = 0.8
    BATCH_SAVINGS_RATE = 0.3
    CACHE_SAVINGS_RATE = 0.2
    COST_PER_AI_VISION_CALL = 0.1

    def generate_cost_report(
        self,
        project_id: int,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> CostReport:
        if not end_date:
            end_date = datetime.now()
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

    def _get_case_cost_details(self, project_id: int) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        case_stats = []
        for case in cases:
            try:
                stats = self.get_case_cost_statistics(case.id)
                case_stats.append({
                    "case_id": case.id,
                    "case_name": case.title,
                    "total_steps": stats.total_steps,
                    "ai_vision_calls": stats.ai_vision_calls,
                    "cache_hits": stats.cache_hits,
                    "cache_hit_rate": stats.cache_hit_rate,
                    "actual_cost": stats.actual_cost,
                    "cost_savings": stats.cost_savings,
                    "savings_rate": stats.savings_rate
                })
            except Exception as e:
                logger.error(f"获取用例成本详情失败 {case.id}: {e}")
        case_stats.sort(key=lambda x: x['cost_savings'], reverse=True)
        return case_stats

    def _get_daily_cost_statistics(
        self, project_id: int, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        case_ids = [case.id for case in cases]
        if not case_ids:
            return []
        results = self.db.query(
            func.date(TestResult.exec_time).label('date'),
            func.count(TestResult.id).label('execution_count')
        ).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= start_date,
            TestResult.exec_time <= end_date
        ).group_by(
            func.date(TestResult.exec_time)
        ).all()
        daily_stats = []
        for result in results:
            daily_stats.append({
                "date": result.date.isoformat() if result.date else None,
                "execution_count": result.execution_count or 0,
                "total_execution_time": 0
            })
        return daily_stats

    def _generate_cost_optimization_suggestions(
        self, project_id: int, overall_stats: CostStatistics
    ) -> List[Dict[str, Any]]:
        suggestions = []
        if overall_stats.ai_dependency_rate > self.AI_DEPENDENCY_THRESHOLD:
            potential_savings = overall_stats.ai_vision_calls * self.COST_PER_AI_VISION_CALL * self.LOCATOR_SAVINGS_RATE
            suggestions.append({
                "type": "补充元素定位",
                "description": f"AI依赖率较高({overall_stats.ai_dependency_rate}%)，建议为更多步骤补充元素定位信息",
                "potential_savings": round(potential_savings, 2),
                "priority": "high",
                "impact": "可显著降低AI视觉成本"
            })
        if overall_stats.total_steps >= self.BATCH_RECOGNITION_MIN_STEPS:
            batch_savings = overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.BATCH_SAVINGS_RATE
            suggestions.append({
                "type": "启用批量识别",
                "description": "用例步骤较多，建议使用批量元素识别功能",
                "potential_savings": round(batch_savings, 2),
                "priority": "medium",
                "impact": "减少AI调用次数"
            })
        if overall_stats.cache_hit_rate < self.CACHE_HIT_RATE_THRESHOLD:
            cache_savings = overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.CACHE_SAVINGS_RATE
            suggestions.append({
                "type": "优化缓存策略",
                "description": f"缓存命中率较低({overall_stats.cache_hit_rate}%)，建议优化定位缓存策略",
                "potential_savings": round(cache_savings, 2),
                "priority": "medium",
                "impact": "提升缓存利用率"
            })
        return suggestions

    def _get_cost_trend(
        self, project_id: int, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        case_ids = [case.id for case in cases]
        if not case_ids:
            return []
        results = self.db.query(
            extract('year', TestResult.exec_time).label('year'),
            extract('week', TestResult.exec_time).label('week'),
            func.count(TestResult.id).label('execution_count'),
            func.avg(TestResult.execution_time).label('avg_execution_time')
        ).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= start_date,
            TestResult.exec_time <= end_date
        ).group_by(
            extract('year', TestResult.exec_time),
            extract('week', TestResult.exec_time)
        ).order_by(
            extract('year', TestResult.exec_time),
            extract('week', TestResult.exec_time)
        ).all()
        trend = []
        for result in results:
            trend.append({
                "week": f"{result.year}-{result.week:02d}",
                "execution_count": result.execution_count or 0,
                "avg_execution_time": round(result.avg_execution_time or 0, 2)
            })
        return trend
