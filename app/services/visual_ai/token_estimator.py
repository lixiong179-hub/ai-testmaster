"""视觉 Token 估算精确化（Task 10）。

设计目的：
    Visual AI 引擎的 LLM 语义分析调用成本较高，需要在调用前精确估算 Token
    消耗，供 BudgetGuard 预检与成本审计。本模块提供基于图片尺寸、base64
    编码膨胀率与文本 Token 比例的精确估算。

估算模型：
    - 文本 Token：英文 ~4 chars/token，中文 ~2 chars/token，混合取 3 chars/token
    - 图片 base64 Token：base64 编码膨胀率 4/3，DeepSeek 文本模型按文本处理
      base64 字符串，故 image_tokens = base64_length / 3
    - 图片 Vision Token（可选）：GPT-4o 等 Vision 模型按 512x512 tile 计费，
      tiles = ceil(width/512) * ceil(height/512)，每 tile 85 tokens

组件：
    - VisualTokenEstimator : 纯函数估算器，无副作用
    - VisualTokenBudgetGuard: 继承 BaseTokenBudgetGuard，绑定 VISUAL_AI_* 配置
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.common.token_budget import BaseTokenBudgetGuard

# Redis key 前缀模板，按 project_id 隔离
_VISUAL_TOKEN_NAMESPACE_TEMPLATE = "visual_ai:token:{project_id}:"


@dataclass
class TokenEstimate:
    """Token 估算结果。

    Attributes:
        prompt_tokens    : 输入 prompt Token 数（含图片 base64）
        completion_tokens: 预估输出 Token 数
        total_tokens     : 总 Token 数
        image_base64_size: 图片 base64 编码后字节数
        breakdown        : 各组件 Token 明细
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    image_base64_size: int = 0
    breakdown: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.total_tokens = self.prompt_tokens + self.completion_tokens


class VisualTokenEstimator:
    """视觉 Token 估算器。

    提供图片 base64 编码 Token 估算、LLM prompt Token 估算与完整对比流程
    Token 预估。所有方法为纯函数，无副作用，可安全并发调用。

    使用方式：
        estimator = VisualTokenEstimator()
        estimate = estimator.estimate_comparison(
            baseline_bytes=png_bytes,
            current_bytes=png_bytes,
            match_level="strict",
        )
        if budget_guard.check_single_call(estimate.total_tokens):
            raise TokenBudgetExceeded(...)
    """

    # 文本 Token 估算：混合中英文取 3 chars/token
    _CHARS_PER_TOKEN: int = 3
    # base64 编码膨胀率：原始字节 * 4/3
    _BASE64_EXPANSION_RATIO: float = 4.0 / 3.0
    # Vision 模型 tile 大小（像素）
    _VISION_TILE_SIZE: int = 512
    # Vision 模型每 tile Token 数
    _VISION_TOKENS_PER_TILE: int = 85
    # LLM 响应预估 Token 数（视觉分析典型输出）
    _DEFAULT_COMPLETION_TOKENS: int = 300

    def estimate_text_tokens(self, text: str) -> int:
        """估算文本字符串的 Token 数。

        混合中英文场景取 3 chars/token 的经验值。

        Args:
            text: 文本字符串

        Returns:
            int: 预估 Token 数
        """
        if not text:
            return 0
        return max(1, len(text) // self._CHARS_PER_TOKEN)

    def estimate_image_base64_tokens(self, image_bytes: bytes) -> int:
        """估算图片 base64 编码后的 Token 数。

        DeepSeek 等文本模型将 base64 字符串作为文本处理，
        故 Token 数 = base64 字符数 / 3。

        Args:
            image_bytes: 图片原始字节流

        Returns:
            int: 预估 Token 数
        """
        if not image_bytes:
            return 0
        base64_size = int(len(image_bytes) * self._BASE64_EXPANSION_RATIO)
        return max(1, base64_size // self._CHARS_PER_TOKEN)

    def estimate_image_vision_tokens(
        self, width: int, height: int
    ) -> int:
        """估算图片在 Vision 模型（如 GPT-4o）中的 Token 数。

        按 512x512 tile 计费，每 tile 85 tokens。

        Args:
            width: 图片宽度（像素）
            height: 图片高度（像素）

        Returns:
            int: 预估 Token 数
        """
        if width <= 0 or height <= 0:
            return 0
        tiles_x = math.ceil(width / self._VISION_TILE_SIZE)
        tiles_y = math.ceil(height / self._VISION_TILE_SIZE)
        return tiles_x * tiles_y * self._VISION_TOKENS_PER_TILE

    def estimate_image_base64_size(self, image_bytes: bytes) -> int:
        """估算图片 base64 编码后的字节数。"""
        if not image_bytes:
            return 0
        return int(len(image_bytes) * self._BASE64_EXPANSION_RATIO)

    def estimate_llm_analysis(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        system_prompt: str = "",
        extra_context: str = "",
    ) -> TokenEstimate:
        """估算单次 LLM 语义分析的 Token 消耗。

        Args:
            baseline_bytes: 基线截图字节流
            current_bytes: 当前截图字节流
            system_prompt: 系统提示文本
            extra_context: 额外上下文文本（如像素差异指标）

        Returns:
            TokenEstimate: 估算结果
        """
        baseline_tokens = self.estimate_image_base64_tokens(baseline_bytes)
        current_tokens = self.estimate_image_base64_tokens(current_bytes)
        system_tokens = self.estimate_text_tokens(system_prompt)
        context_tokens = self.estimate_text_tokens(extra_context)

        prompt_tokens = baseline_tokens + current_tokens + system_tokens + context_tokens
        completion_tokens = self._DEFAULT_COMPLETION_TOKENS

        return TokenEstimate(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            image_base64_size=self.estimate_image_base64_size(baseline_bytes)
            + self.estimate_image_base64_size(current_bytes),
            breakdown={
                "baseline_image_tokens": baseline_tokens,
                "current_image_tokens": current_tokens,
                "system_prompt_tokens": system_tokens,
                "context_tokens": context_tokens,
                "completion_tokens": completion_tokens,
            },
        )

    def estimate_comparison(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        match_level: str = "strict",
        enable_llm_analysis: bool = True,
    ) -> TokenEstimate:
        """估算完整视觉对比流程的 Token 消耗。

        像素对比不消耗 Token，仅 LLM 语义分析消耗 Token。
        若 enable_llm_analysis=False 或差异低于阈值，返回 0。

        Args:
            baseline_bytes: 基线截图字节流
            current_bytes: 当前截图字节流
            match_level: 对比模式
            enable_llm_analysis: 是否启用 LLM 分析

        Returns:
            TokenEstimate: 估算结果（enable_llm_analysis=False 时为 0）
        """
        if not enable_llm_analysis:
            return TokenEstimate(breakdown={"skipped": "llm_analysis_disabled"})

        # 像素对比不消耗 Token，仅 LLM 分析消耗
        return self.estimate_llm_analysis(
            baseline_bytes=baseline_bytes,
            current_bytes=current_bytes,
            system_prompt="你是视觉回归测试专家，分析两张截图的差异类别与严重性。",
            extra_context=f"match_level={match_level}",
        )


class VisualTokenBudgetGuard(BaseTokenBudgetGuard):
    """Visual AI Token 预算守卫，按 project_id 隔离。

    继承 BaseTokenBudgetGuard 的 Redis 累计 + 内存降级逻辑，
    绑定 VISUAL_AI_LLM_TOKEN_LIMIT（单次上限）与 VISUAL_AI_DAILY_TOKEN_BUDGET（日预算）。

    使用方式：
        guard = VisualTokenBudgetGuard(
            redis_client=redis_client,
            project_id=1,
        )
        estimate = estimator.estimate_comparison(...)
        if guard.check_single_call(estimate.total_tokens):
            raise TokenBudgetExceeded("单次视觉分析 Token 超限")
        guard.consume(actual_cost)
    """

    def __init__(
        self,
        redis_client: Optional[Any],
        *,
        project_id: int,
    ) -> None:
        """注入 Redis 客户端与项目隔离维度。

        Args:
            redis_client: 同步 redis.Redis 实例；为 None 时走内存降级。
            project_id: 项目 ID，用于 Redis key 隔离。
        """
        namespace = _VISUAL_TOKEN_NAMESPACE_TEMPLATE.format(project_id=project_id)
        super().__init__(redis_client=redis_client, namespace=namespace)
        self._project_id = project_id

    def check_single_call(self, token_estimate: int) -> bool:
        """校验单次视觉分析 Token 预估是否超 VISUAL_AI_LLM_TOKEN_LIMIT。

        Args:
            token_estimate: 单次视觉分析预估 Token 消耗。

        Returns:
            bool: True 表示预估超限，应跳过 LLM 分析。
        """
        return token_estimate > settings.VISUAL_AI_LLM_TOKEN_LIMIT

    def is_daily_budget_exhausted(self) -> bool:
        """判断当日累计消耗是否超 VISUAL_AI_DAILY_TOKEN_BUDGET。

        Returns:
            bool: True 表示日预算已耗尽，应降级为仅像素对比。
        """
        return self._get_consumed() >= settings.VISUAL_AI_DAILY_TOKEN_BUDGET


__all__ = [
    "TokenEstimate",
    "VisualTokenEstimator",
    "VisualTokenBudgetGuard",
]
