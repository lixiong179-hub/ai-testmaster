"""图像对比引擎单元测试。

覆盖：
    - compare() 相同图片 0% 差异
    - compare() 不同图片非零差异
    - compare() 尺寸不一致自动缩放
    - compare() enable_llm_analysis=False 跳过 LLM
    - compare() LLM 分析触发（Mock AIClient）
    - _parse_llm_response() 解析 structured output
    - _parse_llm_response() 解析 JSON content
    - _parse_llm_response() 解析失败回退
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest
from PIL import Image

from app.services.visual_ai.comparison_engine import (
    ComparisonEngine,
    ComparisonResult,
    LLMAnalysisResult,
)


# ── 测试辅助 ──


def _make_solid_png(width: int, height: int, color: tuple) -> bytes:
    """生成纯色 PNG 字节流。"""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _MockTokenUsage:
    prompt_tokens: int = 100
    completion_tokens: int = 50
    total_cost_usd: float = 0.001


@dataclass
class _MockAIResponse:
    """模拟 AIClient.complete() 返回值。"""
    content: str = ""
    parsed: Optional[Dict[str, Any]] = None
    usage: Optional[_MockTokenUsage] = None
    model_version: str = "mock-model"
    latency_ms: int = 100
    raw_response: Any = None
    degraded: bool = False


class _MockAIClient:
    """模拟 AIClient，返回预置响应。"""

    def __init__(self, response: _MockAIResponse) -> None:
        self._response = response
        self.call_count = 0

    def complete(self, **kwargs: Any) -> _MockAIResponse:
        self.call_count += 1
        return self._response


# ── ComparisonEngine 测试 ──


class TestComparisonEngine:
    """图像对比引擎测试。"""

    async def test_compare_identical_images_zero_diff(self) -> None:
        """相同图片对比差异为 0%，不触发 LLM。"""
        img_bytes = _make_solid_png(50, 50, (255, 0, 0))
        engine = ComparisonEngine()

        result = await engine.compare(
            baseline_bytes=img_bytes,
            current_bytes=img_bytes,
            match_level="strict",
        )

        assert result.diff_percentage == 0.0
        assert result.diff_pixel_count == 0
        assert result.llm_analysis is None
        assert result.total_token_cost == 0

    async def test_compare_different_images_nonzero_diff(self) -> None:
        """不同图片对比非零差异。"""
        baseline = _make_solid_png(50, 50, (255, 0, 0))
        current = _make_solid_png(50, 50, (0, 0, 255))
        engine = ComparisonEngine(llm_analysis_threshold=100.0)  # 设高阈值避免触发 LLM

        result = await engine.compare(
            baseline_bytes=baseline,
            current_bytes=current,
            match_level="strict",
            enable_llm_analysis=False,
        )

        assert result.diff_percentage == 100.0
        assert result.diff_pixel_count == 2500

    async def test_compare_size_mismatch_auto_resize(self) -> None:
        """尺寸不一致时自动缩放当前图片至基线尺寸。"""
        baseline = _make_solid_png(100, 100, (255, 255, 255))
        current = _make_solid_png(50, 50, (0, 0, 0))
        engine = ComparisonEngine()

        result = await engine.compare(
            baseline_bytes=baseline,
            current_bytes=current,
            match_level="strict",
            enable_llm_analysis=False,
        )

        # 缩放后对比，应该有差异
        assert result.diff_pixel_count > 0
        assert result.total_pixel_count == 10000

    async def test_compare_disable_llm_analysis(self) -> None:
        """enable_llm_analysis=False 时不调用 LLM。"""
        baseline = _make_solid_png(30, 30, (255, 0, 0))
        current = _make_solid_png(30, 30, (0, 0, 255))
        mock_client = _MockAIClient(_MockAIResponse())
        engine = ComparisonEngine(ai_client=mock_client, llm_analysis_threshold=0.0)

        result = await engine.compare(
            baseline_bytes=baseline,
            current_bytes=current,
            match_level="strict",
            enable_llm_analysis=False,
        )

        assert result.llm_analysis is None
        assert mock_client.call_count == 0

    async def test_compare_llm_triggered_above_threshold(self) -> None:
        """差异超过阈值时触发 LLM 语义分析。"""
        baseline = _make_solid_png(30, 30, (255, 0, 0))
        current = _make_solid_png(30, 30, (0, 0, 255))
        llm_response = _MockAIResponse(
            parsed={
                "category": "real_bug",
                "confidence": 0.95,
                "severity": "major",
                "description": "颜色完全变更",
                "suggestion": "检查 CSS 样式",
            },
            usage=_MockTokenUsage(prompt_tokens=100, completion_tokens=50),
        )
        mock_client = _MockAIClient(llm_response)
        engine = ComparisonEngine(ai_client=mock_client, llm_analysis_threshold=1.0)

        result = await engine.compare(
            baseline_bytes=baseline,
            current_bytes=current,
            match_level="strict",
            enable_llm_analysis=True,
        )

        assert result.llm_analysis is not None
        assert result.llm_analysis.category == "real_bug"
        assert result.llm_analysis.confidence == 0.95
        assert result.llm_analysis.severity == "major"
        assert result.llm_analysis.token_cost == 150
        assert result.total_token_cost == 150
        assert result.is_real_bug is True
        assert mock_client.call_count == 1

    async def test_compare_llm_not_triggered_below_threshold(self) -> None:
        """差异低于阈值时不触发 LLM。"""
        img_bytes = _make_solid_png(30, 30, (255, 0, 0))
        mock_client = _MockAIClient(_MockAIResponse())
        engine = ComparisonEngine(ai_client=mock_client, llm_analysis_threshold=10.0)

        result = await engine.compare(
            baseline_bytes=img_bytes,
            current_bytes=img_bytes,
            match_level="strict",
            enable_llm_analysis=True,
        )

        assert result.llm_analysis is None
        assert mock_client.call_count == 0

    async def test_compare_llm_failure_returns_empty_result(self) -> None:
        """LLM 调用失败时返回空分析结果，不阻断对比。"""
        baseline = _make_solid_png(30, 30, (255, 0, 0))
        current = _make_solid_png(30, 30, (0, 0, 255))

        class _FailingClient:
            def complete(self, **kwargs: Any) -> Any:
                raise RuntimeError("LLM 调用失败")

        engine = ComparisonEngine(ai_client=_FailingClient(), llm_analysis_threshold=1.0)

        result = await engine.compare(
            baseline_bytes=baseline,
            current_bytes=current,
            match_level="strict",
            enable_llm_analysis=True,
        )

        assert result.llm_analysis is not None
        assert result.llm_analysis.category == ""
        assert result.llm_analysis.token_cost == 0

    async def test_compare_invalid_image_raises(self) -> None:
        """无效图片字节抛 ValueError。"""
        engine = ComparisonEngine()

        with pytest.raises(ValueError, match="图片加载失败"):
            await engine.compare(
                baseline_bytes=b"not an image",
                current_bytes=b"also not an image",
                match_level="strict",
            )


class TestParseLLMResponse:
    """LLM 响应解析测试。"""

    def test_parse_structured_output(self) -> None:
        """解析 parsed（structured output）字段。"""
        engine = ComparisonEngine()
        response = _MockAIResponse(
            parsed={
                "category": "expected_change",
                "confidence": 0.8,
                "severity": "minor",
                "description": "内容更新",
                "suggestion": "更新基线",
            },
            usage=_MockTokenUsage(prompt_tokens=50, completion_tokens=30),
        )

        result = engine._parse_llm_response(response)

        assert result.category == "expected_change"
        assert result.confidence == 0.8
        assert result.severity == "minor"
        assert result.token_cost == 80

    def test_parse_json_content(self) -> None:
        """解析 content 中的 JSON。"""
        import json

        engine = ComparisonEngine()
        response = _MockAIResponse(
            content=json.dumps({
                "category": "visual_noise",
                "confidence": 0.9,
                "severity": "info",
                "description": "抗锯齿差异",
                "suggestion": "忽略",
            }),
            usage=_MockTokenUsage(prompt_tokens=20, completion_tokens=10),
        )

        result = engine._parse_llm_response(response)

        assert result.category == "visual_noise"
        assert result.confidence == 0.9
        assert result.token_cost == 30

    def test_parse_invalid_content_fallback(self) -> None:
        """无效 JSON 回退为描述文本。"""
        engine = ComparisonEngine()
        response = _MockAIResponse(
            content="这不是 JSON 格式的响应",
            usage=_MockTokenUsage(prompt_tokens=10, completion_tokens=5),
        )

        result = engine._parse_llm_response(response)

        assert result.category == ""
        assert result.description == "这不是 JSON 格式的响应"
        assert result.token_cost == 15


class TestLLMAnalysisResult:
    """LLMAnalysisResult 数据类测试。"""

    def test_to_dict(self) -> None:
        """to_dict 返回完整字段。"""
        result = LLMAnalysisResult(
            category="real_bug",
            confidence=0.9,
            severity="critical",
            description="元素丢失",
            suggestion="检查 DOM",
            token_cost=100,
        )
        d = result.to_dict()
        assert d["category"] == "real_bug"
        assert d["confidence"] == 0.9
        assert d["severity"] == "critical"
        assert d["token_cost"] == 100

    def test_to_json(self) -> None:
        """to_json 返回有效 JSON 字符串。"""
        import json

        result = LLMAnalysisResult(category="real_bug", confidence=0.9)
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["category"] == "real_bug"
        assert parsed["confidence"] == 0.9
