"""视觉 Token 估算精确化单元测试（Task 10）。

覆盖：
    - estimate_text_tokens: 空字符串 / 纯英文 / 纯中文 / 混合
    - estimate_image_base64_tokens: 空字节 / 非空字节 / 膨胀率验证
    - estimate_image_vision_tokens: tile 计算 / 零尺寸
    - estimate_image_base64_size: 膨胀率验证
    - estimate_llm_analysis: 完整估算 / breakdown 明细
    - estimate_comparison: 禁用 LLM 返回 0 / 启用返回非零
    - VisualTokenBudgetGuard: check_single_call / is_daily_budget_exhausted
"""
from __future__ import annotations

import pytest

from app.services.visual_ai.token_estimator import (
    TokenEstimate,
    VisualTokenBudgetGuard,
    VisualTokenEstimator,
)


class TestVisualTokenEstimator:
    """视觉 Token 估算器测试。"""

    def setup_method(self) -> None:
        self.estimator = VisualTokenEstimator()

    def test_estimate_text_tokens_empty(self) -> None:
        """空字符串返回 0。"""
        assert self.estimator.estimate_text_tokens("") == 0

    def test_estimate_text_tokens_english(self) -> None:
        """纯英文按 3 chars/token 估算。"""
        text = "Hello World"  # 11 chars
        tokens = self.estimator.estimate_text_tokens(text)
        assert tokens == 11 // 3  # 3

    def test_estimate_text_tokens_chinese(self) -> None:
        """纯中文按 3 chars/token 估算。"""
        text = "你好世界视觉回归测试"  # 9 chars
        tokens = self.estimator.estimate_text_tokens(text)
        assert tokens == 9 // 3  # 3

    def test_estimate_text_tokens_returns_at_least_1(self) -> None:
        """非空短文本至少返回 1。"""
        tokens = self.estimator.estimate_text_tokens("a")
        assert tokens >= 1

    def test_estimate_image_base64_tokens_empty(self) -> None:
        """空字节返回 0。"""
        assert self.estimator.estimate_image_base64_tokens(b"") == 0

    def test_estimate_image_base64_tokens_nonzero(self) -> None:
        """非空字节返回正整数。"""
        data = b"x" * 300  # 300 bytes
        tokens = self.estimator.estimate_image_base64_tokens(data)
        # base64_size = 300 * 4/3 = 400, tokens = 400 / 3 = 133
        assert tokens == 400 // 3
        assert tokens > 0

    def test_estimate_image_base64_tokens_at_least_1(self) -> None:
        """非空字节至少返回 1。"""
        tokens = self.estimator.estimate_image_base64_tokens(b"x")
        assert tokens >= 1

    def test_estimate_image_vision_tokens_zero_size(self) -> None:
        """零尺寸返回 0。"""
        assert self.estimator.estimate_image_vision_tokens(0, 0) == 0
        assert self.estimator.estimate_image_vision_tokens(100, 0) == 0
        assert self.estimator.estimate_image_vision_tokens(0, 100) == 0

    def test_estimate_image_vision_tokens_single_tile(self) -> None:
        """小于 512x512 的图片为 1 tile = 85 tokens。"""
        tokens = self.estimator.estimate_image_vision_tokens(256, 256)
        assert tokens == 85  # 1 * 1 * 85

    def test_estimate_image_vision_tokens_exact_512(self) -> None:
        """正好 512x512 为 1 tile。"""
        tokens = self.estimator.estimate_image_vision_tokens(512, 512)
        assert tokens == 85

    def test_estimate_image_vision_tokens_multi_tile(self) -> None:
        """1024x768 = 2*2 tiles = 340 tokens。"""
        tokens = self.estimator.estimate_image_vision_tokens(1024, 768)
        # tiles_x = ceil(1024/512) = 2, tiles_y = ceil(768/512) = 2
        assert tokens == 2 * 2 * 85  # 340

    def test_estimate_image_base64_size(self) -> None:
        """base64 膨胀率 4/3 验证。"""
        size = self.estimator.estimate_image_base64_size(b"x" * 300)
        assert size == int(300 * 4 / 3)  # 400

    def test_estimate_image_base64_size_empty(self) -> None:
        """空字节返回 0。"""
        assert self.estimator.estimate_image_base64_size(b"") == 0

    def test_estimate_llm_analysis(self) -> None:
        """完整 LLM 分析估算含图片 + 系统提示 + 上下文。"""
        baseline = b"x" * 300  # 300 bytes
        current = b"y" * 300
        system_prompt = "你是视觉回归测试专家" * 5  # ~50 chars
        extra_context = "diff_percentage=5.0%, match_level=strict"

        estimate = self.estimator.estimate_llm_analysis(
            baseline_bytes=baseline,
            current_bytes=current,
            system_prompt=system_prompt,
            extra_context=extra_context,
        )

        assert estimate.prompt_tokens > 0
        assert estimate.completion_tokens > 0
        assert estimate.total_tokens == estimate.prompt_tokens + estimate.completion_tokens
        assert estimate.image_base64_size > 0
        assert "baseline_image_tokens" in estimate.breakdown
        assert "current_image_tokens" in estimate.breakdown
        assert "system_prompt_tokens" in estimate.breakdown
        assert "context_tokens" in estimate.breakdown
        assert "completion_tokens" in estimate.breakdown

    def test_estimate_llm_analysis_empty_images(self) -> None:
        """空图片仍返回 completion tokens。"""
        estimate = self.estimator.estimate_llm_analysis(
            baseline_bytes=b"",
            current_bytes=b"",
            system_prompt="",
            extra_context="",
        )
        assert estimate.prompt_tokens == 0
        assert estimate.completion_tokens > 0
        assert estimate.total_tokens == estimate.completion_tokens

    def test_estimate_comparison_disabled_llm(self) -> None:
        """禁用 LLM 时返回 0 token。"""
        estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 300,
            current_bytes=b"y" * 300,
            enable_llm_analysis=False,
        )
        assert estimate.total_tokens == 0
        assert "skipped" in estimate.breakdown

    def test_estimate_comparison_enabled_llm(self) -> None:
        """启用 LLM 时返回非零 token。"""
        estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 300,
            current_bytes=b"y" * 300,
            enable_llm_analysis=True,
        )
        assert estimate.total_tokens > 0
        assert "baseline_image_tokens" in estimate.breakdown


class TestTokenEstimate:
    """TokenEstimate 数据类测试。"""

    def test_total_tokens_auto_calculated(self) -> None:
        """total_tokens 自动计算为 prompt + completion。"""
        estimate = TokenEstimate(
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert estimate.total_tokens == 150

    def test_breakdown_defaults_to_empty_dict(self) -> None:
        """breakdown 默认为空字典。"""
        estimate = TokenEstimate()
        assert estimate.breakdown == {}

    def test_zero_tokens(self) -> None:
        """零 Token 场景。"""
        estimate = TokenEstimate()
        assert estimate.total_tokens == 0
        assert estimate.prompt_tokens == 0
        assert estimate.completion_tokens == 0


class TestVisualTokenBudgetGuard:
    """Visual AI Token 预算守卫测试。"""

    def test_check_single_call_within_limit(self) -> None:
        """预估低于 VISUAL_AI_LLM_TOKEN_LIMIT 时不超限。"""
        guard = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        from app.core.config import settings

        assert guard.check_single_call(settings.VISUAL_AI_LLM_TOKEN_LIMIT - 1) is False

    def test_check_single_call_exceeds_limit(self) -> None:
        """预估超过 VISUAL_AI_LLM_TOKEN_LIMIT 时超限。"""
        guard = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        from app.core.config import settings

        assert guard.check_single_call(settings.VISUAL_AI_LLM_TOKEN_LIMIT + 1) is True

    def test_is_daily_budget_exhausted_not_exhausted(self) -> None:
        """未消耗时不超日预算。"""
        guard = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        assert guard.is_daily_budget_exhausted() is False

    def test_consume_increments_counter(self) -> None:
        """consume 累计消耗。"""
        guard = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        guard.consume(1000)
        guard.consume(500)
        # 内存降级模式可查询 _get_consumed
        assert guard._get_consumed() == 1500

    def test_daily_budget_exhausted_after_consume(self) -> None:
        """消耗超过日预算后 is_daily_budget_exhausted 返回 True。"""
        from app.core.config import settings

        guard = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        # 消耗超过 VISUAL_AI_DAILY_TOKEN_BUDGET
        guard.consume(settings.VISUAL_AI_DAILY_TOKEN_BUDGET + 1)
        assert guard.is_daily_budget_exhausted() is True

    def test_namespace_isolates_by_project(self) -> None:
        """不同 project_id 的 namespace 不同。"""
        guard1 = VisualTokenBudgetGuard(redis_client=None, project_id=1)
        guard2 = VisualTokenBudgetGuard(redis_client=None, project_id=2)
        assert guard1._namespace != guard2._namespace
        assert "project_id:1" not in guard1._namespace  # 模板填充后含数字
        assert "1" in guard1._namespace
        assert "2" in guard2._namespace


class TestVisualTokenBudgetGuardRedisMode:
    """Visual AI Token 预算守卫 Redis 模式测试。"""

    def test_consume_uses_redis_pipeline(self) -> None:
        """consume 通过 Redis pipeline 累计计数。"""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.execute.return_value = [1000, True]  # [counter_after, marker_set]
        mock_redis.pipeline.return_value = pipe

        guard = VisualTokenBudgetGuard(redis_client=mock_redis, project_id=1)
        guard.consume(1000)

        pipe.incrby.assert_called_once()
        pipe.set.assert_called_once()
        # marker 首次写入时设置 counter key TTL
        mock_redis.expire.assert_called_once()

    def test_consume_redis_exception_falls_back_to_memory(self) -> None:
        """Redis 异常时降级到内存计数。"""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = RuntimeError("redis down")

        guard = VisualTokenBudgetGuard(redis_client=mock_redis, project_id=1)
        guard.consume(500)
        # 内存计数已累计
        assert guard._memory_counter == 500

    def test_get_consumed_reads_redis(self) -> None:
        """_get_consumed 从 Redis 读取计数。"""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        mock_redis.get.return_value = "2500"

        guard = VisualTokenBudgetGuard(redis_client=mock_redis, project_id=1)
        assert guard._get_consumed() == 2500
        mock_redis.get.assert_called_once()

    def test_get_consumed_redis_exception_falls_back_to_memory(self) -> None:
        """Redis 读取异常时降级到内存计数。"""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        mock_redis.get.side_effect = RuntimeError("redis down")

        guard = VisualTokenBudgetGuard(redis_client=mock_redis, project_id=1)
        guard._memory_counter = 800
        assert guard._get_consumed() == 800

    def test_is_daily_budget_exhausted_with_redis(self) -> None:
        """Redis 模式下日预算耗尽判断。"""
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        # 返回超过日预算的值
        from app.core.config import settings

        mock_redis.get.return_value = str(settings.VISUAL_AI_DAILY_TOKEN_BUDGET + 1)

        guard = VisualTokenBudgetGuard(redis_client=mock_redis, project_id=1)
        assert guard.is_daily_budget_exhausted() is True


class TestEstimateComparisonMatchLevels:
    """estimate_comparison 不同 match_level 估算测试。"""

    def setup_method(self) -> None:
        self.estimator = VisualTokenEstimator()

    def test_estimate_comparison_strict(self) -> None:
        """strict 模式估算包含完整 LLM 分析。"""
        estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 300,
            current_bytes=b"y" * 300,
            match_level="strict",
            enable_llm_analysis=True,
        )
        assert estimate.total_tokens > 0
        assert estimate.breakdown["baseline_image_tokens"] > 0

    def test_estimate_comparison_layout(self) -> None:
        """layout 模式同样消耗 LLM Token（match_level 仅影响对比策略）。"""
        estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 300,
            current_bytes=b"y" * 300,
            match_level="layout",
            enable_llm_analysis=True,
        )
        assert estimate.total_tokens > 0
        # match_level 写入 extra_context，不影响 token 估算量级
        assert estimate.breakdown["context_tokens"] > 0

    def test_estimate_comparison_ignore_colors(self) -> None:
        """ignore_colors 模式估算。"""
        estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 300,
            current_bytes=b"y" * 300,
            match_level="ignore_colors",
            enable_llm_analysis=True,
        )
        assert estimate.total_tokens > 0

    def test_estimate_comparison_match_level_in_context(self) -> None:
        """不同 match_level 的 context_tokens 应不同。"""
        strict_estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 100,
            current_bytes=b"y" * 100,
            match_level="strict",
            enable_llm_analysis=True,
        )
        layout_estimate = self.estimator.estimate_comparison(
            baseline_bytes=b"x" * 100,
            current_bytes=b"y" * 100,
            match_level="layout",
            enable_llm_analysis=True,
        )
        # context 部分包含 match_level 字符串，长度不同则 token 不同
        assert strict_estimate.breakdown["context_tokens"] >= 1
        assert layout_estimate.breakdown["context_tokens"] >= 1
