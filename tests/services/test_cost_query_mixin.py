import pytest
from app.services.cost_statistics.query_mixin import CostStatisticsQueryMixin
from app.services.cost_statistics.models import CostStatistics
from app.models.test_case import TestCase, TestStep


def _make_case(db, testProject, case_no, title):
    case = TestCase(
        project_id=testProject.id, title=title,
        case_no=case_no, lifecycle_status="active",
        module="成本模块", precondition="无",
        steps_json=[{"step": 1, "action": "操作", "param": ""}],
        expected_result="成功", priority=2, case_type="UI",
    )
    db.add(case)
    db.flush()
    return case


class TestGetCaseCostStatistics:
    def test_nonexistent_case_raises(self, db):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        with pytest.raises(ValueError, match="不存在"):
            mixin.get_case_cost_statistics(99999)

    def test_case_no_steps(self, db, testProject):
        case = _make_case(db, testProject, "NOSC-001", "no_steps_cost_case")
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        stats = mixin.get_case_cost_statistics(case.id)
        assert stats.total_steps == 0
        assert stats.ai_vision_calls == 0
        assert stats.estimated_cost == 0

    def test_case_with_steps_no_locators(self, db, testProject):
        case = _make_case(db, testProject, "STPC-001", "steps_cost_case")
        step = TestStep(
            test_case_id=case.id, step_number=1, action="click",
            expected_result="成功",
        )
        db.add(step)
        db.flush()
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        stats = mixin.get_case_cost_statistics(case.id)
        assert stats.total_steps == 1
        assert stats.ai_vision_calls == 1


class TestGetProjectCostStatistics:
    def test_empty_project(self, db):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        stats = mixin.get_project_cost_statistics(99999)
        assert stats.total_steps == 0

    def test_project_with_cases(self, db, testProject):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        stats = mixin.get_project_cost_statistics(testProject.id)
        assert isinstance(stats, CostStatistics)


class TestGetCostSummary:
    def test_summary_structure(self, db, testProject):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        summary = mixin.get_cost_summary(testProject.id)
        assert "total_cost" in summary
        assert "cost_savings" in summary
        assert "savings_rate" in summary
        assert "ai_vision_calls" in summary
        assert "cache_hit_rate" in summary
        assert "ai_dependency_rate" in summary
        assert "optimization_potential" in summary


class TestGetCaseCostDetails:
    def test_empty_project(self, db):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        details = mixin._get_case_cost_details(99999)
        assert details == []

    def test_project_with_cases(self, db, testProject):
        mixin = CostStatisticsQueryMixin()
        mixin.db = db
        details = mixin._get_case_cost_details(testProject.id)
        assert isinstance(details, list)
