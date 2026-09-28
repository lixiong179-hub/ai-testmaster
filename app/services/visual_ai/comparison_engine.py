"""图像对比引擎（Task 7）- 像素级对比 + LLM 语义分析。

设计目的：
    ComparisonEngine 整合 Match Level 策略与 LLM 语义对比，提供统一的
    compare 方法。像素对比快速定位差异区域，LLM 语义分析判断差异是否为
    真实缺陷（vs 预期变更/动态内容噪声），降低误报率。

调用流程：
    1. 加载基线截图与当前截图为 PIL.Image
    2. 按 match_level 执行像素对比，生成 PixelDiffResult
    3. 若 diff_percentage >= LLM_ANALYSIS_THRESHOLD 且提供 AIClient，
       执行 LLM 语义分析，判断差异类别与严重性
    4. 返回 ComparisonResult，包含像素指标 + LLM 分析结果

设计原则：
    - 策略注入：MatchLevelStrategy 与 AIClient 均由调用方注入
    - 成本控制：LLM 分析仅在像素差异超过阈值时触发
    - 可观测性：ComparisonResult 包含 token_cost 供成本审计
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from PIL import Image

from app.services.visual_ai.match_level import (
    MatchLevelFactory,
    MatchLevelStrategy,
    PixelDiffResult,
)


@dataclass
class LLMAnalysisResult:
    """LLM 语义分析结果。

    Attributes:
        category     : 差异分类（real_bug/expected_change/dynamic_content/visual_noise）
        confidence   : 分类置信度（0.0-1.0）
        severity     : 严重性（critical/major/minor/info）
        description  : 差异描述
        suggestion   : 处理建议
        token_cost   : LLM Token 消耗
    """

    category: str = ""
    confidence: float = 0.0
    severity: str = "info"
    description: str = ""
    suggestion: str = ""
    token_cost: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """返回字典形式，供持久化到 VisualDiff.llm_analysis。"""
        return {
            "category": self.category,
            "confidence": self.confidence,
            "severity": self.severity,
            "description": self.description,
            "suggestion": self.suggestion,
            "token_cost": self.token_cost,
        }

    def to_json(self) -> str:
        """返回 JSON 字符串，供持久化到 VisualDiff.llm_analysis 字段。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ComparisonResult:
    """图像对比完整结果。

    Attributes:
        pixel_diff      : 像素对比结果
        llm_analysis    : LLM 语义分析结果（未执行时为 None）
        match_level     : 使用的 Match Level
        total_token_cost: 总 Token 消耗（LLM 分析）
    """

    pixel_diff: PixelDiffResult
    llm_analysis: Optional[LLMAnalysisResult] = None
    match_level: str = "strict"
    total_token_cost: int = 0

    @property
    def diff_percentage(self) -> float:
        """差异百分比。"""
        return self.pixel_diff.diff_percentage

    @property
    def diff_pixel_count(self) -> int:
        """差异像素数。"""
        return self.pixel_diff.diff_pixel_count

    @property
    def total_pixel_count(self) -> int:
        """总像素数。"""
        return self.pixel_diff.total_pixel_count

    @property
    def diff_image(self) -> Optional[bytes]:
        """差异图字节流。"""
        return self.pixel_diff.diff_image

    @property
    def is_real_bug(self) -> bool:
        """LLM 判定为真实缺陷（仅在 LLM 分析执行且 category=real_bug 时为 True）。"""
        return self.llm_analysis is not None and self.llm_analysis.category == "real_bug"


class ComparisonEngine:
    """图像对比引擎。

    整合 Match Level 像素对比与 LLM 语义分析，提供统一 compare 方法。

    使用方式：
        engine = ComparisonEngine(ai_client=my_client)
        result = await engine.compare(
            baseline_bytes=baseline_png,
            current_bytes=current_png,
            match_level="strict",
        )
    """

    # LLM 语义分析系统提示
    _LLM_SYSTEM_PROMPT = (
        "你是视觉回归测试专家。对比两张截图的差异，判断差异类别与严重性。\n"
        "差异类别（category）：\n"
        "  - real_bug: 真实缺陷（元素错位/丢失/重叠/文字截断）\n"
        "  - expected_change: 预期变更（内容更新/数据变化）\n"
        "  - dynamic_content: 动态内容（广告/时间戳/轮播图）\n"
        "  - visual_noise: 视觉噪声（抗锯齿/字体渲染差异）\n"
        "严重性（severity）：critical/major/minor/info\n"
        "请以 JSON 格式返回：{\"category\": \"...\", \"confidence\": 0.0, "
        "\"severity\": \"...\", \"description\": \"...\", \"suggestion\": \"...\"}"
    )

    def __init__(
        self,
        ai_client: Optional[Any] = None,
        llm_analysis_threshold: float = 5.0,
        llm_token_limit: int = 2000,
    ) -> None:
        """初始化对比引擎。

        Args:
            ai_client: AI 客户端实例（实现 AIClient 协议），为 None 时跳过 LLM 分析
            llm_analysis_threshold: LLM 语义分析触发阈值（diff_percentage >= 此值时触发）
            llm_token_limit: 单次 LLM 分析 Token 上限
        """
        self._ai_client = ai_client
        self._llm_analysis_threshold = llm_analysis_threshold
        self._llm_token_limit = llm_token_limit

    async def compare(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        match_level: str = "strict",
        enable_llm_analysis: bool = True,
    ) -> ComparisonResult:
        """对比两张截图。

        Args:
            baseline_bytes: 基线截图字节流（PNG/JPEG）
            current_bytes: 当前截图字节流（PNG/JPEG）
            match_level: 对比模式（strict/layout/ignore_colors）
            enable_llm_analysis: 是否启用 LLM 语义分析

        Returns:
            ComparisonResult: 完整对比结果
        """
        # 1. 加载图片
        baseline_img = self._load_image(baseline_bytes)
        current_img = self._load_image(current_bytes)

        # 2. 尺寸对齐（当前截图缩放至基线尺寸）
        if baseline_img.size != current_img.size:
            current_img = current_img.resize(baseline_img.size, Image.LANCZOS)

        # 3. 像素对比
        strategy = MatchLevelFactory.create(match_level)
        pixel_diff = strategy.compare(baseline_img, current_img)

        result = ComparisonResult(
            pixel_diff=pixel_diff,
            match_level=match_level,
            total_token_cost=0,
        )

        # 4. LLM 语义分析（仅在差异超过阈值且启用时触发）
        if (
            enable_llm_analysis
            and self._ai_client is not None
            and pixel_diff.diff_percentage >= self._llm_analysis_threshold
        ):
            llm_result = await self._run_llm_analysis(
                baseline_bytes, current_bytes, pixel_diff
            )
            result.llm_analysis = llm_result
            result.total_token_cost = llm_result.token_cost

        return result

    def _load_image(self, image_bytes: bytes) -> Image.Image:
        """从字节流加载 PIL.Image。

        Raises:
            ValueError: 图片格式无法解析时抛出
        """
        import io

        try:
            return Image.open(io.BytesIO(image_bytes))
        except Exception as exc:
            raise ValueError(f"图片加载失败: {exc}") from exc

    async def _run_llm_analysis(
        self,
        baseline_bytes: bytes,
        current_bytes: bytes,
        pixel_diff: PixelDiffResult,
    ) -> LLMAnalysisResult:
        """执行 LLM 语义分析。

        将两张截图的 base64 编码与像素差异指标发送给 LLM，获取差异分类。
        """
        if self._ai_client is None:
            return LLMAnalysisResult()

        baseline_b64 = base64.b64encode(baseline_bytes).decode("ascii")
        current_b64 = base64.b64encode(current_bytes).decode("ascii")

        prompt = (
            f"基线截图（base64 PNG）:\n{baseline_b64[:500]}...\n\n"
            f"当前截图（base64 PNG）:\n{current_b64[:500]}...\n\n"
            f"像素差异指标: diff_percentage={pixel_diff.diff_percentage:.2f}%, "
            f"diff_pixel_count={pixel_diff.diff_pixel_count}, "
            f"total_pixel_count={pixel_diff.total_pixel_count}\n\n"
            "请分析差异类别、置信度、严重性、描述与处理建议。"
        )

        try:
            response = self._ai_client.complete(
                prompt=prompt,
                system=self._LLM_SYSTEM_PROMPT,
                max_tokens=self._llm_token_limit,
                metadata={"step_name": "visual_ai_llm_analysis"},
            )
            return self._parse_llm_response(response)
        except Exception:
            # LLM 调用失败时不阻断对比流程，返回空结果
            return LLMAnalysisResult()

    def _parse_llm_response(self, response: Any) -> LLMAnalysisResult:
        """解析 LLM 响应为 LLMAnalysisResult。"""
        token_cost = 0
        if hasattr(response, "usage") and response.usage:
            token_cost = getattr(response.usage, "prompt_tokens", 0) + getattr(
                response.usage, "completion_tokens", 0
            )

        content = getattr(response, "content", "") or ""
        parsed = getattr(response, "parsed", None)

        # 优先使用 parsed（structured output）
        if parsed and isinstance(parsed, dict):
            return LLMAnalysisResult(
                category=parsed.get("category", ""),
                confidence=float(parsed.get("confidence", 0.0)),
                severity=parsed.get("severity", "info"),
                description=parsed.get("description", ""),
                suggestion=parsed.get("suggestion", ""),
                token_cost=token_cost,
            )

        # 回退到 content JSON 解析
        try:
            data = json.loads(content)
            return LLMAnalysisResult(
                category=data.get("category", ""),
                confidence=float(data.get("confidence", 0.0)),
                severity=data.get("severity", "info"),
                description=data.get("description", ""),
                suggestion=data.get("suggestion", ""),
                token_cost=token_cost,
            )
        except (json.JSONDecodeError, TypeError):
            return LLMAnalysisResult(
                description=content[:500],
                token_cost=token_cost,
            )


__all__ = [
    "ComparisonEngine",
    "ComparisonResult",
    "PixelDiffResult",
    "LLMAnalysisResult",
]
