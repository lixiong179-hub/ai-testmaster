import pytest
from app.services.case_quality.models import (
    ComplexityScore,
    RedundancyScore,
    CoverageScore,
    QualityReport,
    CaseQualityAnalysisRequest,
    CaseQualityReport,
)


class TestComplexityScore:
    def test_defaults(self):
        score = ComplexityScore()
        assert score.step_count == 0
        assert score.level == "simple"
        assert score.score == 0.0

    def test_to_dict(self):
        score = ComplexityScore(step_count=5, action_variety=3, score=0.75, level="moderate")
        d = score.to_dict()
        assert d["step_count"] == 5
        assert d["level"] == "moderate"
        assert d["score"] == 0.75


class TestRedundancyScore:
    def test_defaults(self):
        score = RedundancyScore()
        assert score.similar_case_count == 0
        assert score.level == "low"

    def test_to_dict(self):
        score = RedundancyScore(
            similar_case_count=3, score=0.6, level="high",
            similar_cases=[{"id": 1, "similarity": 0.9}],
        )
        d = score.to_dict()
        assert d["similar_case_count"] == 3
        assert len(d["similar_cases"]) == 1


class TestCoverageScore:
    def test_defaults(self):
        score = CoverageScore()
        assert score.total_elements == 0
        assert score.coverage_rate == 0.0

    def test_to_dict(self):
        score = CoverageScore(
            total_elements=10, covered_elements=8,
            coverage_rate=0.8, score=80.0, level="high",
        )
        d = score.to_dict()
        assert d["coverage_rate"] == 0.8
        assert d["uncovered_elements"] == 0


class TestQualityReport:
    def test_defaults(self):
        report = QualityReport(case_id=1, case_name="测试")
        assert report.overall_score == 0.0
        assert report.overall_level == "unrated"
        assert report.complexity is None
        assert report.suggestions == []

    def test_to_dict(self):
        report = QualityReport(
            case_id=1, case_name="测试",
            overall_score=85.0, overall_level="good",
            complexity=ComplexityScore(step_count=5),
        )
        d = report.to_dict()
        assert d["overall_score"] == 85.0
        assert d["complexity"]["step_count"] == 5
        assert "analyzed_at" in d

    def test_to_dict_no_sub_scores(self):
        report = QualityReport(case_id=1, case_name="测试")
        d = report.to_dict()
        assert d["complexity"] is None
        assert d["redundancy"] is None
        assert d["coverage"] is None


class TestCaseQualityAnalysisRequest:
    def test_defaults(self):
        req = CaseQualityAnalysisRequest(project_id=1)
        assert req.include_complexity is True
        assert req.include_redundancy is True
        assert req.include_coverage is True
        assert req.test_case_ids == []


class TestCaseQualityReport:
    def test_defaults(self):
        report = CaseQualityReport(project_id=1)
        assert report.total_cases == 0
        assert report.suggestions == []
