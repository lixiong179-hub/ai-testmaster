import pytest
from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
    CaseQualityAnalysisRequest,
    CaseQualityReport,
)
from datetime import datetime


class TestComplexityScore:
    def test_defaults(self):
        score = ComplexityScore()
        assert score.step_count == 0
        assert score.action_variety == 0
        assert score.has_verification is False
        assert score.has_captcha is False
        assert score.score == 0.0
        assert score.level == "simple"

    def test_to_dict(self):
        score = ComplexityScore(step_count=5, score=3.5, level="moderate")
        d = score.to_dict()
        assert d["step_count"] == 5
        assert d["score"] == 3.5
        assert d["level"] == "moderate"

    def test_to_dict_rounds_score(self):
        score = ComplexityScore(score=3.456)
        d = score.to_dict()
        assert d["score"] == 3.46


class TestRedundancyScore:
    def test_defaults(self):
        score = RedundancyScore()
        assert score.similar_case_count == 0
        assert score.duplicate_step_count == 0
        assert score.score == 0.0
        assert score.level == "low"

    def test_to_dict(self):
        score = RedundancyScore(
            similar_case_count=2,
            duplicate_step_count=1,
            score=4.5,
            level="moderate",
        )
        d = score.to_dict()
        assert d["similar_case_count"] == 2
        assert d["duplicate_step_count"] == 1


class TestCoverageScore:
    def test_defaults(self):
        score = CoverageScore()
        assert score.total_elements == 0
        assert score.coverage_rate == 0.0
        assert score.requirement_coverage_rate == 0.0
        assert score.ui_element_coverage_rate == 0.0
        assert score.locator_coverage_rate == 0.0

    def test_to_dict(self):
        score = CoverageScore(
            total_elements=10,
            covered_elements=7,
            coverage_rate=0.7,
            requirement_coverage_rate=1.0,
        )
        d = score.to_dict()
        assert d["total_elements"] == 10
        assert d["coverage_rate"] == 0.7
        assert d["requirement_coverage_rate"] == 1.0

    def test_to_dict_rounds(self):
        score = CoverageScore(coverage_rate=0.7123, score=7.123)
        d = score.to_dict()
        assert d["coverage_rate"] == 0.71
        assert d["score"] == 7.12


class TestQualityReport:
    def test_defaults(self):
        report = QualityReport(case_id=1, case_name="test")
        assert report.overall_score == 0.0
        assert report.overall_level == "unrated"
        assert report.complexity is None
        assert report.redundancy is None
        assert report.coverage is None
        assert report.suggestions == []

    def test_to_dict(self):
        report = QualityReport(
            case_id=1,
            case_name="test",
            overall_score=75.5,
            overall_level="B",
            complexity=ComplexityScore(score=3),
        )
        d = report.to_dict()
        assert d["case_id"] == 1
        assert d["overall_score"] == 75.5
        assert d["complexity"] is not None
        assert d["redundancy"] is None

    def test_to_dict_with_all_scores(self):
        report = QualityReport(
            case_id=1,
            case_name="test",
            complexity=ComplexityScore(),
            redundancy=RedundancyScore(),
            coverage=CoverageScore(),
        )
        d = report.to_dict()
        assert d["complexity"] is not None
        assert d["redundancy"] is not None
        assert d["coverage"] is not None


class TestCaseQualityAnalysisRequest:
    def test_defaults(self):
        req = CaseQualityAnalysisRequest(project_id=1)
        assert req.project_id == 1
        assert req.test_case_ids == []
        assert req.include_complexity is True
        assert req.include_redundancy is True
        assert req.include_coverage is True


class TestCaseQualityReport:
    def test_defaults(self):
        report = CaseQualityReport(project_id=1)
        assert report.project_id == 1
        assert report.total_cases == 0
        assert report.suggestions == []
