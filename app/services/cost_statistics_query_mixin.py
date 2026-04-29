"""成本查询Mixin - 提供AI调用成本的查询与聚合能力。
"""
from typing import Dict, Any
from sqlalchemy.orm import Session, joinedload
from loguru import logger
from app.models.test_case import TestCase, TestStep
from app.services.cost_statistics_models import CostStatistics, _build_empty_statistics


class CostStatisticsQueryMixin:
    COST_PER_AI_VISION_CALL = 0.1

    def get_case_cost_statistics(self, case_id: int) -> CostStatistics:
        test_case = self.db.query(TestCase).filter(
            TestCase.id == case_id
        ).options(
            joinedload(TestCase.test_steps).joinedload(TestStep.element_locator)
        ).first()
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        total_steps = len(steps)
        if total_steps == 0:
            return _build_empty_statistics()
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
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        if not cases:
            return _build_empty_statistics()
        total_stats = {
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
        savings_rate = (cost_savings / total_stats['estimated_cost'] * 100) if total_stats['estimated_cost'] > 0 else 0
        cache_hit_rate = (total_stats['cache_hits'] / total_stats['total_steps'] * 100) if total_stats['total_steps'] > 0 else 0
        ai_dependency_rate = (total_stats['ai_vision_calls'] / total_stats['total_steps'] * 100) if total_stats['total_steps'] > 0 else 0
        return CostStatistics(
            total_steps=total_stats['total_steps'],
            ai_vision_calls=total_stats['ai_vision_calls'],
            cache_hits=total_stats['cache_hits'],
            css_selector_used=total_stats['css_selector_used'],
            xpath_used=total_stats['xpath_used'],
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
