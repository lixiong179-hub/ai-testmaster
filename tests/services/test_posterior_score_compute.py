import pytest
from app.services.posterior_score_service import (
    compute_posterior_score,
    PosteriorInput,
    PosteriorResult,
    KEEP_VERDICTS,
    MODIFY_VERDICTS,
)


class TestComputePosteriorScore:
    def test_normal_case_with_review_and_execution(self):
        inp = PosteriorInput(
            case_id=1,
            review_total=10,
            review_keep_count=8,
            review_modify_count=2,
            execution_total=5,
            execution_passed_count=4,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert result.score is not None
        assert not result.skipped
        assert result.review_pass_rate == 0.8
        assert result.execution_pass_rate == 0.8
        assert result.modification_rate == 0.2

    def test_skipped_when_below_min_executions(self):
        inp = PosteriorInput(
            case_id=2,
            review_total=5,
            review_keep_count=5,
            review_modify_count=0,
            execution_total=1,
            execution_passed_count=1,
        )
        result = compute_posterior_score(inp, min_executions=3)
        assert result.skipped is True
        assert result.score is None
        assert "execution_total" in result.skip_reason

    def test_no_review_data_uses_default_rate(self):
        inp = PosteriorInput(
            case_id=3,
            review_total=0,
            review_keep_count=0,
            review_modify_count=0,
            execution_total=5,
            execution_passed_count=5,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert not result.skipped
        assert result.no_review_data is True
        assert result.review_pass_rate == 0.5
        assert result.modification_rate == 0.0

    def test_zero_execution_pass_rate(self):
        inp = PosteriorInput(
            case_id=4,
            review_total=5,
            review_keep_count=0,
            review_modify_count=5,
            execution_total=5,
            execution_passed_count=0,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert result.score is not None
        assert result.execution_pass_rate == 0.0

    def test_score_bounded_between_0_and_100(self):
        inp = PosteriorInput(
            case_id=5,
            review_total=10,
            review_keep_count=10,
            review_modify_count=0,
            execution_total=10,
            execution_passed_count=10,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert 0.0 <= result.score <= 100.0

    def test_custom_weights(self):
        inp = PosteriorInput(
            case_id=6,
            review_total=10,
            review_keep_count=5,
            review_modify_count=5,
            execution_total=5,
            execution_passed_count=5,
        )
        result = compute_posterior_score(
            inp, w_review=1.0, w_execution=0.0, w_modification=0.0, min_executions=1,
        )
        assert result.score == 50.0

    def test_all_modify_verdicts(self):
        inp = PosteriorInput(
            case_id=7,
            review_total=10,
            review_keep_count=0,
            review_modify_count=10,
            execution_total=5,
            execution_passed_count=5,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert result.modification_rate == 1.0
        assert result.score is not None

    def test_min_executions_default(self):
        inp = PosteriorInput(
            case_id=8,
            review_total=0,
            review_keep_count=0,
            review_modify_count=0,
            execution_total=0,
            execution_passed_count=0,
        )
        result = compute_posterior_score(inp)
        assert result.skipped is True


class TestKeepAndModifyVerdicts:
    def test_keep_verdicts_contains_keep(self):
        assert "keep" in KEEP_VERDICTS

    def test_modify_verdicts_contains_expected(self):
        assert "needs_modify" in MODIFY_VERDICTS
        assert "locator_broken" in MODIFY_VERDICTS
        assert "locator_and_modify" in MODIFY_VERDICTS
