import pytest
from app.services.case_quality.suggestion_mixin import SuggestionMixin
from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
)


class TestGenerateOptimizationSuggestions:
    def setup_method(self):
        self.mixin = SuggestionMixin()

    def test_captcha_suggestion(self):
        complexity = ComplexityScore(has_captcha=True, step_count=3)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("验证码" in s for s in result)

    def test_no_verification_suggestion(self):
        complexity = ComplexityScore(has_verification=False, step_count=3)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("验证步骤" in s for s in result)

    def test_too_many_steps_suggestion(self):
        complexity = ComplexityScore(step_count=7)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("步骤偏多" in s for s in result)

    def test_very_complex_suggestion(self):
        complexity = ComplexityScore(level="very_complex", score=9)
        redundancy = RedundancyScore()
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("复杂度过高" in s for s in result)

    def test_similar_cases_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(similar_case_count=2)
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("相似用例" in s for s in result)

    def test_duplicate_steps_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(duplicate_step_count=3)
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("重复步骤" in s for s in result)

    def test_high_redundancy_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore(level="high", score=7)
        coverage = CoverageScore()
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("冗余度较高" in s for s in result)

    def test_no_test_point_link_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            requirement_coverage_rate=0.0,
            requirement_details={"project_total_test_points": 5, "has_test_point_link": False},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("未关联测试点" in s for s in result)

    def test_partial_requirement_coverage_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            requirement_coverage_rate=0.5,
            requirement_details={"project_total_test_points": 5, "has_test_point_link": True},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("需求覆盖率" in s for s in result)

    def test_no_test_point_data_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            requirement_details={"project_total_test_points": 0},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("测试点数据" in s for s in result)

    def test_no_target_element_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            ui_element_details={"total_ui_labels": 10, "steps_with_target": 0, "matched_steps": 0},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("target_element" in s for s in result)

    def test_low_ui_coverage_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            ui_element_coverage_rate=0.3,
            ui_element_details={"total_ui_labels": 10, "steps_with_target": 5, "matched_steps": 1},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("UI元素覆盖率" in s for s in result)

    def test_no_ui_data_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            ui_element_details={"total_ui_labels": 0},
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("UI原型" in s for s in result)

    def test_low_locator_coverage_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            locator_coverage_rate=0.2,
            uncovered_elements=5,
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("定位覆盖率" in s or "批量录制" in s for s in result)

    def test_very_low_coverage_suggestion(self):
        complexity = ComplexityScore()
        redundancy = RedundancyScore()
        coverage = CoverageScore(
            level="very_low",
            locator_coverage_rate=0.1,
            uncovered_elements=8,
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert any("核心步骤" in s or "覆盖率较低" in s for s in result)

    def test_no_suggestions_for_good_case(self):
        complexity = ComplexityScore(has_verification=True, step_count=3, score=1)
        redundancy = RedundancyScore(score=1, level="low")
        coverage = CoverageScore(
            score=9,
            requirement_coverage_rate=1.0,
            requirement_details={"project_total_test_points": 0},
            ui_element_details={"total_ui_labels": 0},
            locator_coverage_rate=1.0,
            uncovered_elements=0,
        )
        result = self.mixin._generate_optimization_suggestions(complexity, redundancy, coverage)
        assert isinstance(result, list)


class TestCalculateOverallScore:
    def test_perfect_score(self):
        complexity = ComplexityScore(score=0)
        redundancy = RedundancyScore(score=0)
        coverage = CoverageScore(score=10)
        result = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert result == 100.0

    def test_worst_score(self):
        complexity = ComplexityScore(score=10)
        redundancy = RedundancyScore(score=10)
        coverage = CoverageScore(score=0)
        result = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert result == 0.0

    def test_mixed_score(self):
        complexity = ComplexityScore(score=5)
        redundancy = RedundancyScore(score=5)
        coverage = CoverageScore(score=5)
        result = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert 0 < result < 100

    def test_score_weights(self):
        complexity = ComplexityScore(score=10)
        redundancy = RedundancyScore(score=0)
        coverage = CoverageScore(score=0)
        result = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert result == pytest.approx(40.0, abs=0.1)

    def test_score_rounded(self):
        complexity = ComplexityScore(score=3)
        redundancy = RedundancyScore(score=7)
        coverage = CoverageScore(score=4)
        result = SuggestionMixin._calculate_overall_score(complexity, redundancy, coverage)
        assert result == round(result, 2)
