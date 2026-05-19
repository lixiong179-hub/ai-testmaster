"""成本统计查询Mixin - 用例/项目成本统计与趋势查询。"""
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.services.cost_statistics.models import CostStatistics


class CostStatisticsQueryMixin:
    """成本统计查询：用例级、项目级、趋势、摘要。"""

    COST_PER_AI_VISION_CALL = 0.1

    def get_case_cost_statistics(self, case_id: int) -> CostStatistics:
        test_case = self.db.query(TestCase).filter(
            TestCase.id == case_id, TestCase.is_deleted.is_(False)
        ).options(
            joinedload(TestCase.test_steps).joinedload(TestStep.element_locator)
        ).first()
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")

        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        total_steps = len(steps)

        if total_steps == 0:
            return CostStatistics(
                total_steps=0, ai_vision_calls=0, cache_hits=0,
                css_selector_used=0, xpath_used=0,
                estimated_cost=0, actual_cost=0, cost_savings=0,
                savings_rate=0, cache_hit_rate=0, ai_dependency_rate=0
            )

        ai_vision_calls = 0
        cache_hits = 0
        css_selector_used = 0
        xpath_used = 0

        for step in steps:
            locator = step.element_locator if hasattr(step, 'element_locator') else None
            if locator:
                if locator.css_selector:
                    css_selector_used += 1
                    cache_hits += 1
                elif locator.xpath:
                    xpath_used += 1
                    cache_hits += 1
                else:
                    ai_vision_calls += 1
            else:
                ai_vision_calls += 1

        estimated_cost = total_steps * self.COST_PER_AI_VISION_CALL
        actual_cost = ai_vision_calls * self.COST_PER_AI_VISION_CALL
        cost_savings = estimated_cost - actual_cost
        savings_rate = (cost_savings / estimated_cost * 100) if estimated_cost > 0 else 0
        cache_hit_rate = (cache_hits / total_steps * 100) if total_steps > 0 else 0
        ai_dependency_rate = (ai_vision_calls / total_steps * 100) if total_steps > 0 else 0

        return CostStatistics(
            total_steps=total_steps,
            ai_vision_calls=ai_vision_calls,
            cache_hits=cache_hits,
            css_selector_used=css_selector_used,
            xpath_used=xpath_used,
            estimated_cost=round(estimated_cost, 2),
            actual_cost=round(actual_cost, 2),
            cost_savings=round(cost_savings, 2),
            savings_rate=round(savings_rate, 1),
            cache_hit_rate=round(cache_hit_rate, 1),
            ai_dependency_rate=round(ai_dependency_rate, 1)
        )

    def get_project_cost_statistics(self, project_id: int) -> CostStatistics:
        cases = self.db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted.is_(False)).all()
        if not cases:
            return CostStatistics(
                total_steps=0, ai_vision_calls=0, cache_hits=0,
                css_selector_used=0, xpath_used=0,
                estimated_cost=0, actual_cost=0, cost_savings=0,
                savings_rate=0, cache_hit_rate=0, ai_dependency_rate=0
            )

        total_stats: Dict[str, float] = {
            'total_steps': 0, 'ai_vision_calls': 0, 'cache_hits': 0,
            'css_selector_used': 0, 'xpath_used': 0,
            'estimated_cost': 0, 'actual_cost': 0
        }

        for case in cases:
            try:
                stats = self.get_case_cost_statistics(case.id)
                total_stats['total_steps'] += stats.total_steps
                total_stats['ai_vision_calls'] += stats.ai_vision_calls
                total_stats['cache_hits'] += stats.cache_hits
                total_stats['css_selector_used'] += stats.css_selector_used
                total_stats['xpath_used'] += stats.xpath_used
                total_stats['estimated_cost'] += stats.estimated_cost
                total_stats['actual_cost'] += stats.actual_cost
            except Exception as e:
                logger.error(f"统计用例成本失败 {case.id}: {e}")

        cost_savings = total_stats['estimated_cost'] - total_stats['actual_cost']
        savings_rate = (
            cost_savings / total_stats['estimated_cost'] * 100
        ) if total_stats['estimated_cost'] > 0 else 0
        cache_hit_rate = (
            total_stats['cache_hits'] / total_stats['total_steps'] * 100
        ) if total_stats['total_steps'] > 0 else 0
        ai_dependency_rate = (
            total_stats['ai_vision_calls'] / total_stats['total_steps'] * 100
        ) if total_stats['total_steps'] > 0 else 0

        return CostStatistics(
            total_steps=int(total_stats['total_steps']),
            ai_vision_calls=int(total_stats['ai_vision_calls']),
            cache_hits=int(total_stats['cache_hits']),
            css_selector_used=int(total_stats['css_selector_used']),
            xpath_used=int(total_stats['xpath_used']),
            estimated_cost=round(total_stats['estimated_cost'], 2),
            actual_cost=round(total_stats['actual_cost'], 2),
            cost_savings=round(cost_savings, 2),
            savings_rate=round(savings_rate, 1),
            cache_hit_rate=round(cache_hit_rate, 1),
            ai_dependency_rate=round(ai_dependency_rate, 1)
        )

    def get_cost_summary(self, project_id: int) -> Dict[str, Any]:
        stats = self.get_project_cost_statistics(project_id)
        return {
            "total_cost": stats.actual_cost,
            "cost_savings": stats.cost_savings,
            "savings_rate": stats.savings_rate,
            "ai_vision_calls": stats.ai_vision_calls,
            "cache_hit_rate": stats.cache_hit_rate,
            "ai_dependency_rate": stats.ai_dependency_rate,
            "optimization_potential": stats.cost_savings > 0
        }

    def _get_case_cost_details(self, project_id: int) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted.is_(False)).all()
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
        cases = self.db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted.is_(False)).all()
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
        ).group_by(func.date(TestResult.exec_time)).all()

        return [
            {
                "date": result.date.isoformat() if result.date else None,
                "execution_count": result.execution_count or 0,
                "total_execution_time": 0
            }
            for result in results
        ]

    def _get_cost_trend(
        self, project_id: int, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        cases = self.db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.is_deleted.is_(False)).all()
        case_ids = [case.id for case in cases]
        if not case_ids:
            return []

        results = self.db.query(
            func.yearweek(TestResult.exec_time).label('week'),
            func.count(TestResult.id).label('execution_count'),
            func.avg(TestResult.execution_time).label('avg_execution_time')
        ).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= start_date,
            TestResult.exec_time <= end_date
        ).group_by(func.yearweek(TestResult.exec_time)).order_by(
            func.yearweek(TestResult.exec_time)
        ).all()

        return [
            {
                "week": result.week,
                "execution_count": result.execution_count or 0,
                "avg_execution_time": round(result.avg_execution_time or 0, 2)
            }
            for result in results
        ]
