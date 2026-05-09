"""后验质量�?�?纯计算逻辑单元测试

覆盖 compute_posterior_score 的正常路径、边界场景、异常路径，
不依赖数据库�?"""
import pytest

from app.services.posterior_score_service import (
    PosteriorInput,
    PosteriorResult,
    compute_posterior_score,
    KEEP_VERDICTS,
    MODIFY_VERDICTS,
)
from app.pipelines.steps.reconciliation import MergedAction


class TestVerdictSetsFromEnum:
    """验证 KEEP_VERDICTS / MODIFY_VERDICTS 从枚举派�?""

    def test_keep_verdicts_matches_enum(self):
        assert MergedAction.KEEP.value in KEEP_VERDICTS
        assert len(KEEP_VERDICTS) == 1

    def test_modify_verdicts_matches_enum(self):
        expected = {
            MergedAction.NEEDS_MODIFY.value,
            MergedAction.LOCATOR_BROKEN.value,
            MergedAction.LOCATOR_AND_MODIFY.value,
        }
        assert MODIFY_VERDICTS == expected


class TestComputePosteriorScoreNormal:
    """正常路径测试"""

    def test_all_perfect(self):
        inp = PosteriorInput(
            case_id=1, review_total=5, review_keep_count=5,
            review_modify_count=0, execution_total=10, execution_passed_count=10,
        )
        result = compute_posterior_score(inp)
        assert result.score == 100.0
        assert result.skipped is False
        assert result.no_review_data is False

    def test_all_fail(self):
        inp = PosteriorInput(
            case_id=2, review_total=5, review_keep_count=0,
            review_modify_count=5, execution_total=10, execution_passed_count=0,
        )
        result = compute_posterior_score(inp)
        assert result.score == 0.0
        assert result.skipped is False

    def test_mixed_signals(self):
        inp = PosteriorInput(
            case_id=3, review_total=10, review_keep_count=7,
            review_modify_count=3, execution_total=8, execution_passed_count=6,
        )
        result = compute_posterior_score(inp)
        expected = (0.5 * 0.7 + 0.3 * 0.75 + 0.2 * 0.7) * 100
        assert result.score == round(expected, 2)


class TestComputePosteriorScoreSkip:
    """跳过逻辑测试"""

    def test_skip_below_min_executions(self):
        inp = PosteriorInput(
            case_id=4, review_total=5, review_keep_count=5,
            review_modify_count=0, execution_total=2, execution_passed_count=2,
        )
        result = compute_posterior_score(inp, min_executions=3)
        assert result.score is None
        assert result.skipped is True
        assert "execution_total(2)" in result.skip_reason

    def test_exact_min_executions(self):
        inp = PosteriorInput(
            case_id=5, review_total=1, review_keep_count=1,
            review_modify_count=0, execution_total=3, execution_passed_count=3,
        )
        result = compute_posterior_score(inp, min_executions=3)
        assert result.score is not None
        assert result.skipped is False


class TestComputePosteriorScoreNoReview:
    """无评审数据时默认值测�?""

    def test_no_reviews_defaults_to_neutral(self):
        inp = PosteriorInput(
            case_id=6, review_total=0, review_keep_count=0,
            review_modify_count=0, execution_total=5, execution_passed_count=4,
        )
        result = compute_posterior_score(inp)
        assert result.review_pass_rate == 0.5
        assert result.modification_rate == 0.0
        assert result.no_review_data is True
        expected = (0.5 * 0.5 + 0.3 * 0.8 + 0.2 * 1.0) * 100
        assert result.score == round(expected, 2)


class TestComputePosteriorScoreClamping:
    """分数钳位测试"""

    def test_score_clamped_to_100(self):
        inp = PosteriorInput(
            case_id=7, review_total=10, review_keep_count=10,
            review_modify_count=0, execution_total=10, execution_passed_count=10,
        )
        result = compute_posterior_score(inp, w_review=0.6, w_execution=0.4, w_modification=0.2)
        assert result.score <= 100.0

    def test_score_clamped_to_0(self):
        inp = PosteriorInput(
            case_id=8, review_total=10, review_keep_count=0,
            review_modify_count=10, execution_total=10, execution_passed_count=0,
        )
        result = compute_posterior_score(inp, w_review=0.5, w_execution=0.3, w_modification=-0.1)
        assert result.score >= 0.0


class TestComputePosteriorScoreEdgeCases:
    """边界场景测试"""

    def test_zero_execution_passed(self):
        inp = PosteriorInput(
            case_id=9, review_total=5, review_keep_count=5,
            review_modify_count=0, execution_total=5, execution_passed_count=0,
        )
        result = compute_posterior_score(inp)
        assert result.execution_pass_rate == 0.0
        expected = (0.5 * 1.0 + 0.3 * 0.0 + 0.2 * 1.0) * 100
        assert result.score == round(expected, 2)

    def test_single_execution_meets_min_1(self):
        inp = PosteriorInput(
            case_id=100, review_total=1, review_keep_count=1,
            review_modify_count=0, execution_total=1, execution_passed_count=1,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert result.score == 100.0

    def test_large_numbers(self):
        inp = PosteriorInput(
            case_id=200, review_total=10000, review_keep_count=8000,
            review_modify_count=2000, execution_total=50000, execution_passed_count=40000,
        )
        result = compute_posterior_score(inp)
        assert result.score is not None
        assert 0 <= result.score <= 100

    def test_all_modify_verdicts(self):
        inp = PosteriorInput(
            case_id=300, review_total=10, review_keep_count=0,
            review_modify_count=10, execution_total=5, execution_passed_count=5,
        )
        result = compute_posterior_score(inp)
        assert result.modification_rate == 1.0
        expected = (0.5 * 0.0 + 0.3 * 1.0 + 0.2 * 0.0) * 100
        assert result.score == round(expected, 2)

    def test_negative_case_id(self):
        inp = PosteriorInput(
            case_id=-1, review_total=1, review_keep_count=1,
            review_modify_count=0, execution_total=3, execution_passed_count=3,
        )
        result = compute_posterior_score(inp)
        assert result.score == 100.0

    def test_empty_case_ids_list_returns_early(self):
        """�?case_ids 列表应在 fetch 层返回空，此处验�?compute 不受影响"""
        inp = PosteriorInput(
            case_id=999, review_total=1, review_keep_count=1,
            review_modify_count=0, execution_total=3, execution_passed_count=3,
        )
        result = compute_posterior_score(inp)
        assert result.score is not None
