import pytest
from app.services.case_quality.coverage_mixin import (
    CoverageMixin,
    _REQUIREMENT_WEIGHT,
    _UI_ELEMENT_WEIGHT,
    _LOCATOR_WEIGHT,
    _MIN_UI_LABEL_LEN,
    _TEST_POINT_PRIORITY_WEIGHTS,
)


class FakeStep:
    def __init__(self, action="click", target_element=None, id=1):
        self.action = action
        self.target_element = target_element
        self.id = id


class FakeCase:
    def __init__(self, test_point_id=None):
        self.test_point_id = test_point_id


class TestCalcRequirementCoverage:
    def test_no_test_points(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=None, ctx={},
        )
        assert rate == 0.0
        assert details["available"] is False

    def test_case_with_high_priority_test_point(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=FakeCase(test_point_id=1),
            ctx={"project_test_point_priorities": {1: 1}},
        )
        assert rate == 1.0
        assert details["has_test_point_link"] is True

    def test_case_with_medium_priority(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=FakeCase(test_point_id=2),
            ctx={"project_test_point_priorities": {2: 2}},
        )
        assert rate == 0.7

    def test_case_with_low_priority(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=FakeCase(test_point_id=3),
            ctx={"project_test_point_priorities": {3: 3}},
        )
        assert rate == 0.4

    def test_case_no_test_point_link(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=FakeCase(test_point_id=None),
            ctx={"project_test_point_priorities": {1: 1}},
        )
        assert rate == 0.0
        assert details["has_test_point_link"] is False

    def test_case_with_unknown_priority(self):
        rate, details = CoverageMixin._calc_requirement_coverage(
            case=FakeCase(test_point_id=4),
            ctx={"project_test_point_priorities": {4: 99}},
        )
        assert rate == 0.4


class TestCalcUiElementCoverage:
    def test_no_ui_labels(self):
        steps = [FakeStep(target_element="登录按钮")]
        rate, details = CoverageMixin._calc_ui_element_coverage(steps, ctx={})
        assert rate == 0.0
        assert details["available"] is False

    def test_no_target_elements(self):
        steps = [FakeStep(target_element=None)]
        rate, details = CoverageMixin._calc_ui_element_coverage(
            steps, ctx={"project_ui_labels": {"登录"}},
        )
        assert rate == 0.0
        assert details["available"] is False

    def test_matching_ui_labels(self):
        steps = [FakeStep(target_element="登录按钮")]
        rate, details = CoverageMixin._calc_ui_element_coverage(
            steps, ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate == 1.0
        assert details["matched_steps"] == 1

    def test_partial_match(self):
        steps = [
            FakeStep(target_element="登录按钮", id=1),
            FakeStep(target_element="退出按钮", id=2),
        ]
        rate, details = CoverageMixin._calc_ui_element_coverage(
            steps, ctx={"project_ui_labels": {"登录按钮"}},
        )
        assert rate == 0.5

    def test_empty_target_element(self):
        steps = [FakeStep(target_element="")]
        rate, details = CoverageMixin._calc_ui_element_coverage(
            steps, ctx={"project_ui_labels": {"登录"}},
        )
        assert details["steps_with_target"] == 0


class TestIsUiMatch:
    def test_exact_match(self):
        assert CoverageMixin._is_ui_match("登录", "登录") is True

    def test_substring_match(self):
        assert CoverageMixin._is_ui_match("登录按钮", "登录") is True

    def test_reverse_substring(self):
        assert CoverageMixin._is_ui_match("登录", "登录按钮") is True

    def test_no_match(self):
        assert CoverageMixin._is_ui_match("退出", "登录") is False

    def test_short_label_exact_only(self):
        assert CoverageMixin._is_ui_match("是否", "是") is False
        assert CoverageMixin._is_ui_match("是", "是") is True

    def test_empty_target(self):
        assert CoverageMixin._is_ui_match("", "登录") is False

    def test_empty_label(self):
        assert CoverageMixin._is_ui_match("登录", "") is False


class TestAggregateCoverage:
    def test_all_dimensions(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=1.0, req_available=True,
            ui_rate=0.5, ui_available=True,
            loc_rate=0.8, loc_available=True,
        )
        expected = (1.0 * _REQUIREMENT_WEIGHT + 0.5 * _UI_ELEMENT_WEIGHT + 0.8 * _LOCATOR_WEIGHT)
        assert rate == pytest.approx(expected, rel=0.01)

    def test_no_dimensions(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0, req_available=False,
            ui_rate=0, ui_available=False,
            loc_rate=0, loc_available=False,
        )
        assert rate == 0.0

    def test_only_locator(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=0, req_available=False,
            ui_rate=0, ui_available=False,
            loc_rate=1.0, loc_available=True,
        )
        assert rate == 1.0

    def test_req_and_locator(self):
        rate = CoverageMixin._aggregate_coverage(
            req_rate=1.0, req_available=True,
            ui_rate=0, ui_available=False,
            loc_rate=0.5, loc_available=True,
        )
        weight_sum = _REQUIREMENT_WEIGHT + _LOCATOR_WEIGHT
        expected = (1.0 * _REQUIREMENT_WEIGHT + 0.5 * _LOCATOR_WEIGHT) / weight_sum
        assert rate == pytest.approx(expected, rel=0.01)


class TestCoverageLevel:
    def test_high(self):
        assert CoverageMixin._coverage_level(0.95) == "high"

    def test_moderate(self):
        assert CoverageMixin._coverage_level(0.75) == "moderate"

    def test_low(self):
        assert CoverageMixin._coverage_level(0.55) == "low"

    def test_very_low(self):
        assert CoverageMixin._coverage_level(0.3) == "very_low"

    def test_boundary_high(self):
        assert CoverageMixin._coverage_level(0.9) == "high"

    def test_boundary_moderate(self):
        assert CoverageMixin._coverage_level(0.7) == "moderate"

    def test_boundary_low(self):
        assert CoverageMixin._coverage_level(0.5) == "low"


class TestAnalyzeCoverage:
    def test_empty_steps(self):
        mixin = CoverageMixin()
        score = mixin._analyze_coverage(steps=[], coverage_context={}, case=None)
        assert score.total_elements == 0
        assert score.coverage_rate == 0.0

    def test_with_locator_context(self):
        mixin = CoverageMixin()
        steps = [FakeStep(id=1), FakeStep(id=2)]
        from app.models.element_locator import ElementLocator
        loc1 = ElementLocator(step_id=1, css_selector="btn")
        ctx = {"locators_by_step": {1: [loc1]}}
        score = mixin._analyze_coverage(steps=steps, coverage_context=ctx, case=None)
        assert score.locator_coverage_rate == 0.5
