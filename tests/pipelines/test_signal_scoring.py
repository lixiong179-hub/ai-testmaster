import pytest
from app.pipelines.steps._signal_scoring import (
    _score_to_grade,
    _check_user_confirmed,
    _compute_analyzer_score,
    _compute_prior_score,
)


class TestScoreToGrade:
    def test_a_grade(self):
        assert _score_to_grade(90) == "A"

    def test_a_boundary(self):
        assert _score_to_grade(85) == "A"

    def test_b_grade(self):
        assert _score_to_grade(70) == "B"

    def test_b_boundary(self):
        assert _score_to_grade(65) == "B"

    def test_c_grade(self):
        assert _score_to_grade(50) == "C"

    def test_c_boundary(self):
        assert _score_to_grade(45) == "C"

    def test_d_grade(self):
        assert _score_to_grade(30) == "D"

    def test_zero(self):
        assert _score_to_grade(0) == "D"

    def test_hundred(self):
        assert _score_to_grade(100) == "A"


class TestCheckUserConfirmed:
    def test_none_db(self):
        assert _check_user_confirmed(None, 1) is False


class TestComputeAnalyzerScore:
    def test_good_analyzer(self):
        analyzer = type("Analyzer", (), {
            "analyze_case": lambda self, data: {
                "complexity_score": 2,
                "coverage_score": 8,
                "redundancy_score": 1,
                "suggestion_count": 1,
            }
        })()
        score, grade, breakdown = _compute_analyzer_score(analyzer, {"title": "test"})
        assert 0 <= score <= 100
        assert grade in ("A", "B", "C", "D")
        assert "analyzer_complexity" in breakdown

    def test_bad_analyzer(self):
        analyzer = type("Analyzer", (), {
            "analyze_case": lambda self, data: {
                "complexity_score": 9,
                "coverage_score": 1,
                "redundancy_score": 8,
                "suggestion_count": 10,
            }
        })()
        score, grade, breakdown = _compute_analyzer_score(analyzer, {})
        assert grade in ("C", "D")

    def test_score_bounded(self):
        analyzer = type("Analyzer", (), {
            "analyze_case": lambda self, data: {
                "complexity_score": 0,
                "coverage_score": 10,
                "redundancy_score": 0,
                "suggestion_count": 0,
            }
        })()
        score, _, _ = _compute_analyzer_score(analyzer, {})
        assert 0 <= score <= 100


class TestComputePriorScore:
    def test_all_signals_present(self):
        score, grade, breakdown = _compute_prior_score(
            case_data={"title": "登录测试", "steps": [], "expected_result": "", "precondition": ""},
            tp={"id": 1},
            signals={"has_prd": True, "has_testpoints": True, "has_ui": True, "is_old_project": True},
            inferred={},
            aligned={"conflict_count": 0},
            iteration_id=1,
            db=None,
        )
        assert 0 <= score <= 100
        assert "signal_score" in breakdown
        assert "content_score" in breakdown

    def test_no_signals(self):
        score, grade, breakdown = _compute_prior_score(
            case_data={"title": "", "steps": [], "expected_result": "", "precondition": ""},
            tp={},
            signals={"has_prd": False, "has_testpoints": False, "has_ui": False, "is_old_project": False},
            inferred={"confidence": 0.5},
            aligned={"conflict_count": 5},
            iteration_id=1,
            db=None,
        )
        assert 0 <= score <= 100
        assert breakdown.get("conflict_penalty", 0) < 0

    def test_none_signals(self):
        score, _, _ = _compute_prior_score(
            case_data={"title": "test", "steps": [], "expected_result": "", "precondition": ""},
            tp={},
            signals=None,
            inferred=None,
            aligned=None,
            iteration_id=1,
            db=None,
        )
        assert 0 <= score <= 100

    def test_conflict_penalty(self):
        score_no_conflict, _, bd1 = _compute_prior_score(
            case_data={"title": "test", "steps": [], "expected_result": "", "precondition": ""},
            tp={},
            signals={"has_prd": True, "has_testpoints": True, "has_ui": True, "is_old_project": True},
            inferred={},
            aligned={"conflict_count": 0},
            iteration_id=1,
            db=None,
        )
        score_with_conflict, _, bd2 = _compute_prior_score(
            case_data={"title": "test", "steps": [], "expected_result": "", "precondition": ""},
            tp={},
            signals={"has_prd": True, "has_testpoints": True, "has_ui": True, "is_old_project": True},
            inferred={},
            aligned={"conflict_count": 10},
            iteration_id=1,
            db=None,
        )
        assert score_no_conflict >= score_with_conflict

    def test_inferred_confidence(self):
        score, _, breakdown = _compute_prior_score(
            case_data={"title": "test", "steps": [], "expected_result": "", "precondition": ""},
            tp={},
            signals={"has_prd": False, "has_testpoints": False, "has_ui": False, "is_old_project": False},
            inferred={"confidence": 0.8},
            aligned={"conflict_count": 0},
            iteration_id=1,
            db=None,
        )
        assert breakdown.get("inferred_capability_confidence", 0) > 0
