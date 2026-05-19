import pytest
from app.services.cost_statistics.report_mixin import CostStatisticsReportMixin
from app.services.cost_statistics.models import CostStatistics


class TestGenerateCostOptimizationSuggestions:
    def setup_method(self):
        self.mixin = CostStatisticsReportMixin()

    def test_high_ai_dependency_suggestion(self):
        stats = CostStatistics(
            total_steps=10, ai_vision_calls=8, cache_hits=2,
            css_selector_used=1, xpath_used=1,
            estimated_cost=1.0, actual_cost=0.8, cost_savings=0.2,
            savings_rate=20.0, cache_hit_rate=20.0, ai_dependency_rate=80.0,
        )
        suggestions = self.mixin._generate_cost_optimization_suggestions(1, stats)
        types = [s["type"] for s in suggestions]
        assert "补充元素定位" in types

    def test_batch_recognition_suggestion(self):
        stats = CostStatistics(
            total_steps=15, ai_vision_calls=5, cache_hits=10,
            css_selector_used=8, xpath_used=2,
            estimated_cost=1.5, actual_cost=0.5, cost_savings=1.0,
            savings_rate=66.7, cache_hit_rate=66.7, ai_dependency_rate=33.3,
        )
        suggestions = self.mixin._generate_cost_optimization_suggestions(1, stats)
        types = [s["type"] for s in suggestions]
        assert "启用批量识别" in types

    def test_low_cache_hit_suggestion(self):
        stats = CostStatistics(
            total_steps=5, ai_vision_calls=3, cache_hits=2,
            css_selector_used=1, xpath_used=1,
            estimated_cost=0.5, actual_cost=0.3, cost_savings=0.2,
            savings_rate=40.0, cache_hit_rate=40.0, ai_dependency_rate=60.0,
        )
        suggestions = self.mixin._generate_cost_optimization_suggestions(1, stats)
        types = [s["type"] for s in suggestions]
        assert "优化缓存策略" in types

    def test_no_suggestions_for_optimal(self):
        stats = CostStatistics(
            total_steps=5, ai_vision_calls=1, cache_hits=4,
            css_selector_used=3, xpath_used=1,
            estimated_cost=0.5, actual_cost=0.1, cost_savings=0.4,
            savings_rate=80.0, cache_hit_rate=80.0, ai_dependency_rate=20.0,
        )
        suggestions = self.mixin._generate_cost_optimization_suggestions(1, stats)
        assert len(suggestions) == 0

    def test_suggestion_has_priority(self):
        stats = CostStatistics(
            total_steps=10, ai_vision_calls=8, cache_hits=2,
            css_selector_used=1, xpath_used=1,
            estimated_cost=1.0, actual_cost=0.8, cost_savings=0.2,
            savings_rate=20.0, cache_hit_rate=20.0, ai_dependency_rate=80.0,
        )
        suggestions = self.mixin._generate_cost_optimization_suggestions(1, stats)
        for s in suggestions:
            assert "priority" in s
            assert "potential_savings" in s
