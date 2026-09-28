"""三层 Match Level 对比策略单元测试。

覆盖：
    - StrictMatchLevel: 相同图片 0% 差异 / 不同图片非零差异 / 像素阈值
    - LayoutMatchLevel: 相同图片 0% 差异 / 布局变更检测
    - IgnoreColorsMatchLevel: 纯色彩变更 0% 差异 / 亮度变更有差异
    - MatchLevelFactory: 创建策略 / 未知 level 抛异常 / supported_levels
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.visual_ai.match_level import (
    IgnoreColorsMatchLevel,
    LayoutMatchLevel,
    MatchLevelFactory,
    MatchLevelStrategy,
    PixelDiffResult,
    StrictMatchLevel,
)


# ── 测试辅助函数 ──


def _make_solid_image(width: int, height: int, color: tuple) -> bytes:
    """生成纯色 PNG 图片字节流。"""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_image_with_rect(
    width: int, height: int, bg_color: tuple, rect: tuple, rect_color: tuple
) -> bytes:
    """生成带矩形的 PNG 图片字节流。

    Args:
        bg_color: 背景色 (R, G, B)
        rect: 矩形区域 (x, y, w, h)
        rect_color: 矩形颜色 (R, G, B)
    """
    img = Image.new("RGB", (width, height), bg_color)
    x, y, w, h = rect
    for px in range(x, x + w):
        for py in range(y, y + h):
            img.putpixel((px, py), rect_color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_image(image_bytes: bytes) -> Image.Image:
    """从字节流加载 PIL.Image。"""
    return Image.open(io.BytesIO(image_bytes))


# ── StrictMatchLevel 测试 ──


class TestStrictMatchLevel:
    """Strict Match Level 像素级严格对比测试。"""

    def test_identical_images_zero_diff(self) -> None:
        """相同图片对比差异为 0%。"""
        img_bytes = _make_solid_image(100, 100, (255, 0, 0))
        baseline = _load_image(img_bytes)
        current = _load_image(img_bytes)

        strategy = StrictMatchLevel()
        result = strategy.compare(baseline, current)

        assert result.diff_percentage == 0.0
        assert result.diff_pixel_count == 0
        assert result.total_pixel_count == 10000
        assert not result.has_diff
        assert result.diff_image is None

    def test_different_images_nonzero_diff(self) -> None:
        """不同颜色图片对比差异为 100%。"""
        baseline = _load_image(_make_solid_image(50, 50, (255, 0, 0)))
        current = _load_image(_make_solid_image(50, 50, (0, 0, 255)))

        strategy = StrictMatchLevel()
        result = strategy.compare(baseline, current)

        assert result.diff_percentage == 100.0
        assert result.diff_pixel_count == 2500
        assert result.has_diff
        assert result.diff_image is not None

    def test_partial_diff(self) -> None:
        """部分区域差异：10x10 矩形变更 = 100/2500 = 4%。"""
        baseline = _load_image(_make_solid_image(50, 50, (255, 255, 255)))
        current = _load_image(_make_image_with_rect(50, 50, (255, 255, 255), (0, 0, 10, 10), (0, 0, 0)))

        strategy = StrictMatchLevel()
        result = strategy.compare(baseline, current)

        assert result.diff_pixel_count == 100
        assert result.total_pixel_count == 2500
        assert result.diff_percentage == pytest.approx(4.0, abs=0.01)

    def test_pixel_threshold_filters_noise(self) -> None:
        """像素阈值过滤微小差异。"""
        baseline = _load_image(_make_solid_image(20, 20, (100, 100, 100)))
        # 亮度差异 2（102 vs 100），threshold=5 时应过滤
        current = _load_image(_make_solid_image(20, 20, (102, 102, 102)))

        strategy = StrictMatchLevel(pixel_threshold=5)
        result = strategy.compare(baseline, current)

        assert result.diff_pixel_count == 0

    def test_size_mismatch_raises(self) -> None:
        """尺寸不一致时抛 ValueError。"""
        baseline = _load_image(_make_solid_image(50, 50, (0, 0, 0)))
        current = _load_image(_make_solid_image(60, 60, (0, 0, 0)))

        strategy = StrictMatchLevel()
        with pytest.raises(ValueError, match="尺寸不一致"):
            strategy.compare(baseline, current)


# ── LayoutMatchLevel 测试 ──


class TestLayoutMatchLevel:
    """Layout Match Level 布局对比测试。"""

    def test_identical_images_zero_diff(self) -> None:
        """相同图片布局对比差异为 0。"""
        img_bytes = _make_solid_image(64, 64, (200, 200, 200))
        baseline = _load_image(img_bytes)
        current = _load_image(img_bytes)

        strategy = LayoutMatchLevel(grid_size=8)
        result = strategy.compare(baseline, current)

        assert result.diff_pixel_count == 0
        assert not result.has_diff

    def test_layout_change_detected(self) -> None:
        """布局变更（大面积亮度变化）被检测到。"""
        baseline = _load_image(_make_solid_image(64, 64, (255, 255, 255)))
        current = _load_image(_make_solid_image(64, 64, (0, 0, 0)))

        strategy = LayoutMatchLevel(grid_size=8, brightness_threshold=15)
        result = strategy.compare(baseline, current)

        assert result.has_diff
        assert result.diff_pixel_count > 0


# ── IgnoreColorsMatchLevel 测试 ──


class TestIgnoreColorsMatchLevel:
    """Ignore Colors Match Level 色彩忽略对比测试。"""

    def test_color_only_change_zero_diff(self) -> None:
        """纯色彩变更（亮度相同）差异为 0。"""
        # 红色与蓝色亮度可能不同，使用同亮度色
        # ITU-R 601-2 luma: 0.299R + 0.587G + 0.114B
        # (100, 0, 0) → 29.9, (0, 50, 0) → 29.35 接近
        baseline = _load_image(_make_solid_image(30, 30, (100, 50, 50)))
        current = _load_image(_make_solid_image(30, 30, (100, 50, 50)))

        strategy = IgnoreColorsMatchLevel(brightness_threshold=5)
        result = strategy.compare(baseline, current)

        assert result.diff_pixel_count == 0

    def test_brightness_change_detected(self) -> None:
        """亮度变更有差异。"""
        baseline = _load_image(_make_solid_image(30, 30, (50, 50, 50)))
        current = _load_image(_make_solid_image(30, 30, (200, 200, 200)))

        strategy = IgnoreColorsMatchLevel(brightness_threshold=5)
        result = strategy.compare(baseline, current)

        assert result.has_diff
        assert result.diff_pixel_count > 0


# ── MatchLevelFactory 测试 ──


class TestMatchLevelFactory:
    """Match Level 工厂测试。"""

    def test_create_strict(self) -> None:
        """工厂创建 StrictMatchLevel 实例。"""
        strategy = MatchLevelFactory.create("strict")
        assert isinstance(strategy, StrictMatchLevel)
        assert isinstance(strategy, MatchLevelStrategy)

    def test_create_layout(self) -> None:
        """工厂创建 LayoutMatchLevel 实例。"""
        strategy = MatchLevelFactory.create("layout")
        assert isinstance(strategy, LayoutMatchLevel)

    def test_create_ignore_colors(self) -> None:
        """工厂创建 IgnoreColorsMatchLevel 实例。"""
        strategy = MatchLevelFactory.create("ignore_colors")
        assert isinstance(strategy, IgnoreColorsMatchLevel)

    def test_create_invalid_level_raises(self) -> None:
        """未知 match_level 抛 ValueError。"""
        with pytest.raises(ValueError, match="未知 Match Level"):
            MatchLevelFactory.create("invalid_level")

    def test_supported_levels(self) -> None:
        """supported_levels 返回三种策略。"""
        levels = MatchLevelFactory.supported_levels()
        assert "strict" in levels
        assert "layout" in levels
        assert "ignore_colors" in levels
        assert len(levels) == 3


# ── PixelDiffResult 测试 ──


class TestPixelDiffResult:
    """PixelDiffResult 数据类测试。"""

    def test_has_diff_true_when_pixels_exist(self) -> None:
        """有差异像素时 has_diff 为 True。"""
        result = PixelDiffResult(
            diff_percentage=5.0,
            diff_pixel_count=100,
            total_pixel_count=2000,
        )
        assert result.has_diff is True

    def test_has_diff_false_when_no_pixels(self) -> None:
        """无差异像素时 has_diff 为 False。"""
        result = PixelDiffResult(
            diff_percentage=0.0,
            diff_pixel_count=0,
            total_pixel_count=2000,
        )
        assert result.has_diff is False
