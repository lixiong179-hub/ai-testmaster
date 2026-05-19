"""M4-T01 QualityGate 先验质量分 单元测试

覆盖 plan §7.1 信号完整性公式的所有分支和边界场景。
"""
import pytest

from app.pipelines.steps.quality_gate import _compute_prior_score, _score_to_grade


_MOCK_DB = None


def _make_signals(**overrides):
    defaults = {
        "has_prd": False,
        "has_testpoints": False,
        "has_ui": False,
        "is_old_project": False,
    }
    defaults.update(overrides)
    return defaults


def _make_inferred(confidence: float = 0.0):
    return {"confidence": confidence}


def _make_aligned(conflict_count: int = 0):
    return {"conflict_count": conflict_count}


def _call(**kwargs):
    return _compute_prior_score(
        case_data=kwargs.get("case_data", {}),
        tp=kwargs.get("tp", {}),
        signals=kwargs.get("signals", _make_signals()),
        inferred=kwargs.get("inferred", _make_inferred()),
        aligned=kwargs.get("aligned", _make_aligned()),
        iteration_id=kwargs.get("iteration_id", 0),
        db=kwargs.get("db", _MOCK_DB),
    )


class TestScoreToGrade:
    def test_grade_a(self):
        assert _score_to_grade(85.0) == "A"
        assert _score_to_grade(100.0) == "A"

    def test_grade_b(self):
        assert _score_to_grade(65.0) == "B"
        assert _score_to_grade(84.99) == "B"

    def test_grade_c(self):
        assert _score_to_grade(45.0) == "C"
        assert _score_to_grade(64.99) == "C"

    def test_grade_d(self):
        assert _score_to_grade(0.0) == "D"
        assert _score_to_grade(44.99) == "D"

    def test_boundary_a_b(self):
        assert _score_to_grade(85) == "A"
        assert _score_to_grade(84) == "B"

    def test_boundary_b_c(self):
        assert _score_to_grade(65) == "B"
        assert _score_to_grade(64) == "C"

    def test_boundary_c_d(self):
        assert _score_to_grade(45) == "C"
        assert _score_to_grade(44) == "D"


class TestFullSignals:
    def test_all_signals_present(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 34.0
        assert grade == "D"
        assert breakdown["prd"] == 25.0
        assert breakdown["testpoints"] == 20.0
        assert breakdown["ui_prototype"] == 25.0
        assert breakdown["history"] == 15.0

    def test_all_signals_no_prd(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=False, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 29.4
        assert grade == "D"
        assert breakdown["inferred_capability_confidence"] == 13.5
        assert breakdown["testpoints"] == 20.0
        assert breakdown["ui_prototype"] == 25.0
        assert breakdown["history"] == 15.0

    def test_all_signals_no_testpoints(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=False, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 26.0
        assert grade == "D"
        assert breakdown["testpoints"] == 0.0

    def test_all_signals_no_ui(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=False, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 24.0
        assert grade == "D"
        assert breakdown["ui_prototype"] == 0.0

    def test_all_signals_no_history(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=False),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 30.0
        assert grade == "D"
        assert breakdown["history"] == 5.0


class TestNoSignals:
    def test_no_signals_at_all(self):
        score, grade, breakdown = _call(
            signals=_make_signals(),
            inferred=_make_inferred(0.0),
            aligned=_make_aligned(0),
        )
        assert score == 2.0
        assert grade == "D"
        assert breakdown["inferred_capability_confidence"] == 0.0
        assert breakdown["testpoints"] == 0.0
        assert breakdown["ui_prototype"] == 0.0
        assert breakdown["history"] == 5.0

    def test_no_signals_high_inferred_confidence(self):
        score, grade, _ = _call(
            signals=_make_signals(),
            inferred=_make_inferred(1.0),
            aligned=_make_aligned(0),
        )
        assert score == 8.0
        assert grade == "D"


class TestInferredConfidenceScaling:
    def test_max_confidence(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(1.0),
            aligned=_make_aligned(0),
        )
        assert breakdown["inferred_capability_confidence"] == 15.0
        assert score == 18.0
        assert grade == "D"

    def test_mid_confidence(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(0.5),
            aligned=_make_aligned(0),
        )
        assert breakdown["inferred_capability_confidence"] == 7.5

    def test_zero_confidence(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(0.0),
            aligned=_make_aligned(0),
        )
        assert breakdown["inferred_capability_confidence"] == 0.0

    def test_inferred_not_used_when_prd_present(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True),
            inferred=_make_inferred(1.0),
            aligned=_make_aligned(0),
        )
        assert "prd" in breakdown
        assert "inferred_capability_confidence" not in breakdown
        assert breakdown["prd"] == 25.0


class TestConflictPenalty:
    def test_no_conflicts(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert breakdown["conflict_penalty"] == -0.0
        assert score == 34.0

    def test_one_conflict(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(1),
        )
        assert breakdown["conflict_penalty"] == -3.0
        assert score == 32.8

    def test_five_conflicts_capped(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(5),
        )
        assert breakdown["conflict_penalty"] == -15.0
        assert score == 28.0

    def test_ten_conflicts_capped(self):
        score, _, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(10),
        )
        assert breakdown["conflict_penalty"] == -15.0
        assert score == 28.0

    def test_conflicts_push_to_d(self):
        score, grade, _ = _call(
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(5),
        )
        assert score == 11.4
        assert grade == "D"


class TestScoreClamping:
    def test_score_not_negative(self):
        score, _, _ = _call(
            signals=_make_signals(),
            inferred=_make_inferred(0.0),
            aligned=_make_aligned(10),
        )
        assert score >= 0.0

    def test_score_not_above_100(self):
        score, _, _ = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True, is_old_project=True),
            inferred=_make_inferred(1.0),
            aligned=_make_aligned(0),
        )
        assert score <= 100.0

    def test_score_rounded_to_two_decimals(self):
        score, _, _ = _call(
            signals=_make_signals(has_ui=True, is_old_project=True),
            inferred=_make_inferred(0.5),
            aligned=_make_aligned(1),
        )
        assert score == round(score, 2)
        assert isinstance(score, float)


class TestNoneArtifactSafety:
    def test_none_signals(self):
        score, grade, _ = _compute_prior_score(
            case_data={}, tp={},
            signals=None, inferred={}, aligned={},
            iteration_id=0, db=_MOCK_DB,
        )
        assert score >= 0.0

    def test_none_inferred(self):
        score, grade, _ = _compute_prior_score(
            case_data={}, tp={},
            signals=_make_signals(has_ui=True),
            inferred=None, aligned={},
            iteration_id=0, db=_MOCK_DB,
        )
        assert score >= 0.0

    def test_none_aligned(self):
        score, grade, _ = _compute_prior_score(
            case_data={}, tp={},
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(0.8), aligned=None,
            iteration_id=0, db=_MOCK_DB,
        )
        assert score >= 0.0


class TestVariousScenarios:
    def test_scenario_1_all_signals(self):
        score, grade, _ = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True, has_ui=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert score == 30.0
        assert grade == "D"

    def test_scenario_2_prd_only(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_prd=True, has_testpoints=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert breakdown["ui_prototype"] == 0.0
        assert breakdown["history"] == 5.0
        assert score == 20.0
        assert grade == "D"

    def test_scenario_3_ui_only(self):
        score, grade, breakdown = _call(
            signals=_make_signals(has_ui=True),
            inferred=_make_inferred(0.9),
            aligned=_make_aligned(0),
        )
        assert breakdown["ui_prototype"] == 25.0
        assert breakdown["inferred_capability_confidence"] == 13.5
        assert breakdown["history"] == 5.0
        assert score == 17.4
        assert grade == "D"
