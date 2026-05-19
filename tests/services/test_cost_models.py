import pytest
from app.services.cost_statistics.models import CostStatistics, CostReportData, CostStatisticsRequest
from datetime import datetime


class TestCostStatistics:
    def test_creation(self):
        stats = CostStatistics(
            total_steps=10,
            ai_vision_calls=3,
            cache_hits=7,
            css_selector_used=5,
            xpath_used=2,
            estimated_cost=1.0,
            actual_cost=0.3,
            cost_savings=0.7,
            savings_rate=70.0,
            cache_hit_rate=70.0,
            ai_dependency_rate=30.0,
        )
        assert stats.total_steps == 10
        assert stats.ai_vision_calls == 3
        assert stats.cache_hits == 7

    def test_default_created_at(self):
        stats = CostStatistics(
            total_steps=0, ai_vision_calls=0, cache_hits=0,
            css_selector_used=0, xpath_used=0,
            estimated_cost=0, actual_cost=0, cost_savings=0,
            savings_rate=0, cache_hit_rate=0, ai_dependency_rate=0,
        )
        assert isinstance(stats.created_at, datetime)


class TestCostReportData:
    def test_defaults(self):
        data = CostReportData(project_id=1)
        assert data.project_id == 1
        assert data.total_cost == 0.0
        assert data.total_tokens == 0
        assert data.daily_costs == []

    def test_avg_cost_per_requests_property(self):
        data = CostReportData(project_id=1, avg_cost_per_request=0.05)
        assert data.avg_cost_per_requests == 0.05


class TestCostStatisticsRequest:
    def test_creation(self):
        req = CostStatisticsRequest(
            project_id=1,
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 31),
        )
        assert req.project_id == 1
        assert req.group_by == "day"

    def test_custom_group_by(self):
        req = CostStatisticsRequest(
            project_id=1,
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 31),
            group_by="week",
        )
        assert req.group_by == "week"
