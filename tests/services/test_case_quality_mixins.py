import pytest
from app.services.case_quality.complexity_mixin import ComplexityMixin
from app.services.case_quality.suggestion_mixin import SuggestionMixin
from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
)


class FakeStep:
    def __init__(self, action):
        self.action = action


class FakePreconditionStep:
    pass


class TestComplexityMixin:
    def setup_method(self):
        self.mixin = ComplexityMixin()

    def test_empty_steps(self):
        score = self.mixin._analyze_complexity([], [])
        assert score.step_count == 0
        assert score.level == "simple"

    def test_simple_case(self):
        steps = [FakeStep("点击登录按钮"), FakeStep("验证页面跳转")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.step_count == 2
        assert score.has_verification is True
        assert score.action_variety >= 1

    def test_complex_case_with_captcha(self):
        steps = [
            FakeStep("输入用户名"),
            FakeStep("输入密码"),
            FakeStep("验证码"),
            FakeStep("点击登录"),
            FakeStep("验证首页"),
        ]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.has_captcha is True
        assert score.has_verification is True

    def test_very_complex_case(self):
        steps = [FakeStep(f"步骤{i}") for i in range(12)]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.level in ("complex", "very_complex")

    def test_with_precondition_steps(self):
        steps = [FakeStep("点击按钮")]
        preconditions = [FakePreconditionStep(), FakePreconditionStep()]
        score = self.mixin._analyze_complexity(steps, preconditions)
        assert score.precondition_count == 2

    def test_navigate_action(self):
        steps = [FakeStep("导航到首页")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 1

    def test_wait_action(self):
        steps = [FakeStep("等待3秒")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 1

    def test_scroll_action(self):
        steps = [FakeStep("滚动到底部")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 1

    def test_hover_action(self):
        steps = [FakeStep("悬停菜单")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 1

    def test_select_action(self):
        steps = [FakeStep("选择下拉选项")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 1

    def test_english_actions(self):
        steps = [FakeStep("click button"), FakeStep("input text"), FakeStep("verify result")]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.action_variety >= 3

    def test_score_bounded(self):
        steps = [FakeStep("输入数据") for _ in range(20)]
        score = self.mixin._analyze_complexity(steps, [])
        assert score.score <= 10.0


class TestSuggestionMixin:
    def setup_method(self):
        self.mixin = SuggestionMixin()

    def test_captcha_suggestion(self):
        complexity = ComplexityScore(has_captcha=True, step_count=5)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("验证码" in s for s in suggestions)

    def test_no_verification_suggestion(self):
        complexity = ComplexityScore(has_verification=False, step_count=3)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("验证步骤" in s for s in suggestions)

    def test_too_many_steps_suggestion(self):
        complexity = ComplexityScore(step_count=12)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("步骤过多" in s for s in suggestions)

    def test_very_complex_suggestion(self):
        complexity = ComplexityScore(level="very_complex", score=9)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("复杂度过高" in s for s in suggestions)

    def test_similar_cases_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(similar_case_count=3)
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("相似用例" in s for s in suggestions)

    def test_duplicate_steps_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(duplicate_step_count=2)
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("重复步骤" in s for s in suggestions)

    def test_high_redundancy_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(level="high")
        coverage = CoverageScore()
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("冗余度较高" in s for s in suggestions)

    def test_no_test_point_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(requirement_details={"project_total_test_points": 0})
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("测试点数据" in s for s in suggestions)

    def test_no_ui_data_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(ui_element_details={"total_ui_labels": 0})
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("UI原型" in s for s in suggestions)

    def test_low_locator_coverage_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            locator_coverage_rate=0.2, uncovered_elements=5,
            level="low",
        )
        suggestions = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("定位覆盖率" in s for s in suggestions)


class TestCalculateOverallScore:
    def test_perfect_scores(self):
        complexity = ComplexityScore(score=0)
        redundancy = RedundancyScore(score=0)
        coverage = CoverageScore(score=10)
        overall = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert overall == 100.0

    def test_worst_scores(self):
        complexity = ComplexityScore(score=10)
        redundancy = RedundancyScore(score=10)
        coverage = CoverageScore(score=0)
        overall = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert overall == 0.0

    def test_mixed_scores(self):
        complexity = ComplexityScore(score=5)
        redundancy = RedundancyScore(score=3)
        coverage = CoverageScore(score=7)
        overall = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert 0 < overall < 100

    def test_score_rounded_to_2_decimals(self):
        complexity = ComplexityScore(score=3)
        redundancy = RedundancyScore(score=4)
        coverage = CoverageScore(score=6)
        overall = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert overall == round(overall, 2)
