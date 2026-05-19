import pytest
from app.services.cost_statistics.models import CostStatistics, CostReport, CostStatisticsRequest, CostReportData
from datetime import datetime


class TestCostStatistics:
    def test_create(self):
        stats = CostStatistics(
            total_steps=10, ai_vision_calls=3, cache_hits=7,
            css_selector_used=5, xpath_used=2,
            estimated_cost=1.0, actual_cost=0.3, cost_savings=0.7,
            savings_rate=70.0, cache_hit_rate=70.0, ai_dependency_rate=30.0,
        )
        assert stats.total_steps == 10
        assert stats.ai_vision_calls == 3
        assert stats.estimated_cost == 1.0

    def test_default_created_at(self):
        stats = CostStatistics(
            total_steps=0, ai_vision_calls=0, cache_hits=0,
            css_selector_used=0, xpath_used=0,
            estimated_cost=0, actual_cost=0, cost_savings=0,
            savings_rate=0, cache_hit_rate=0, ai_dependency_rate=0,
        )
        assert stats.created_at is not None


class TestCostReport:
    def test_create(self):
        stats = CostStatistics(
            total_steps=0, ai_vision_calls=0, cache_hits=0,
            css_selector_used=0, xpath_used=0,
            estimated_cost=0, actual_cost=0, cost_savings=0,
            savings_rate=0, cache_hit_rate=0, ai_dependency_rate=0,
        )
        report = CostReport(
            report_id="COST-1-20260101",
            project_id=1,
            start_date=datetime.now(),
            end_date=datetime.now(),
            overall_statistics=stats,
            case_statistics=[],
            daily_statistics=[],
            optimization_suggestions=[],
            trend_data=[],
        )
        assert report.report_id == "COST-1-20260101"
        assert report.generated_at is not None


class TestCostStatisticsRequest:
    def test_create(self):
        req = CostStatisticsRequest(
            project_id=1,
            start_date=datetime.now(),
            end_date=datetime.now(),
        )
        assert req.group_by == "day"


class TestCostReportData:
    def test_create(self):
        data = CostReportData(project_id=1)
        assert data.total_cost == 0.0
        assert data.avg_cost_per_request == 0.0

    def test_avg_cost_per_requests_property(self):
        data = CostReportData(project_id=1, avg_cost_per_request=0.5)
        assert data.avg_cost_per_requests == 0.5
