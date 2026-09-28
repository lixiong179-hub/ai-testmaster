"""三层 Match Level 对比策略（Task 6）。

设计目的：
    参考 Applitools Visual AI 的三层 Match Level，为不同场景提供可配置的
    视觉对比精度。Strict 适合精确像素回归，Layout 适合响应式布局验证，
    IgnoreColors 适合主题切换场景。

三层 Match Level 语义：
    - Strict        : 像素级严格对比，RGB 三通道逐像素比较，任何差异均计入
    - Layout        : 布局对比，将图像划分为网格区域，比较区域的位置与尺寸，
                      忽略区域内的像素细节差异（抗噪声）
    - IgnoreColors  : 色彩忽略对比，先转灰度再逐像素比较，适合主题切换场景

设计原则：
    - 策略模式：MatchLevelStrategy 抽象基类定义 compare 接口，子类实现具体算法
    - 工厂模式：MatchLevelFactory 按 match_level 字符串返回对应策略实例
    - 纯函数：compare 方法无副作用，输入两张 PIL.Image，输出 PixelDiffResult
"""
from __future__ import annotations

import io
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageChops


class PixelDiffResult:
    """像素对比结果。

    Attributes:
        diff_percentage   : 差异百分比（0.0-100.0）
        diff_pixel_count  : 差异像素数
        total_pixel_count : 总像素数
        diff_image        : 差异图（高亮差异区域的叠加图），无差异时为 None
    """

    def __init__(
        self,
        diff_percentage: float,
        diff_pixel_count: int,
        total_pixel_count: int,
        diff_image: Optional[bytes] = None,
    ) -> None:
        self.diff_percentage = diff_percentage
        self.diff_pixel_count = diff_pixel_count
        self.total_pixel_count = total_pixel_count
        self.diff_image = diff_image

    @property
    def has_diff(self) -> bool:
        """是否存在差异。"""
        return self.diff_pixel_count > 0

    def __repr__(self) -> str:
        return (
            f"<PixelDiffResult(diff={self.diff_percentage:.2f}%, "
            f"pixels={self.diff_pixel_count}/{self.total_pixel_count})>"
        )


class MatchLevelStrategy(ABC):
    """Match Level 策略抽象基类。

    子类必须实现 compare 方法，接收两张 PIL.Image 返回 PixelDiffResult。
    所有策略均要求两张图片尺寸一致，不一致时由调用方负责缩放。
    """

    @abstractmethod
    def compare(self, baseline: Image.Image, current: Image.Image) -> PixelDiffResult:
        """对比两张图片，返回像素差异结果。

        Args:
            baseline: 基线截图（PIL.Image）
            current: 当前截图（PIL.Image）

        Returns:
            PixelDiffResult: 像素差异结果
        """
        raise NotImplementedError

    @staticmethod
    def _ensure_same_size(baseline: Image.Image, current: Image.Image) -> Tuple[int, int]:
        """校验两张图片尺寸一致，返回 (width, height)。

        Raises:
            ValueError: 尺寸不一致时抛出
        """
        if baseline.size != current.size:
            raise ValueError(
                f"图片尺寸不一致: baseline={baseline.size}, current={current.size}"
            )
        return baseline.size

    @staticmethod
    def _generate_diff_image(
        baseline: Image.Image, current: Image.Image, diff_mask: np.ndarray
    ) -> Optional[bytes]:
        """生成差异图：基线图上用红色高亮差异区域。

        Args:
            baseline: 基线截图
            current: 当前截图（用于叠加）
            diff_mask: 差异像素掩码（True=差异）

        Returns:
            差异图 PNG 字节流，无差异时返回 None
        """
        if not diff_mask.any():
            return None
        diff_overlay = Image.new("RGBA", baseline.size, (0, 0, 0, 0))
        overlay_array = np.array(diff_overlay)
        # 差异区域填充半透明红色
        overlay_array[diff_mask] = [255, 0, 0, 128]
        diff_overlay = Image.fromarray(overlay_array)
        result = Image.alpha_composite(baseline.convert("RGBA"), diff_overlay)
        buf = io.BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()


class StrictMatchLevel(MatchLevelStrategy):
    """Strict Match Level - 像素级严格对比。

    RGB 三通道逐像素比较，任何通道差异超过阈值均计入差异像素。
    适合精确像素回归测试，对渲染噪声敏感。
    """

    def __init__(self, pixel_threshold: int = 0) -> None:
        """初始化 Strict 策略。

        Args:
            pixel_threshold: 单像素 RGB 差异阈值（0-255），默认 0 即严格相等。
                             抗轻微渲染噪声可设为 3-5。
        """
        self._pixel_threshold = pixel_threshold

    def compare(self, baseline: Image.Image, current: Image.Image) -> PixelDiffResult:
        """逐像素对比 RGB 三通道。"""
        width, height = self._ensure_same_size(baseline, current)
        total_pixels = width * height

        base_arr = np.array(baseline.convert("RGB"), dtype=np.int16)
        curr_arr = np.array(current.convert("RGB"), dtype=np.int16)

        # 计算每个像素 RGB 通道差异的最大值
        diff = np.abs(base_arr - curr_arr).max(axis=2)
        diff_mask = diff > self._pixel_threshold
        diff_count = int(diff_mask.sum())

        diff_percentage = (diff_count / total_pixels * 100.0) if total_pixels > 0 else 0.0
        diff_image = self._generate_diff_image(baseline, current, diff_mask)

        return PixelDiffResult(
            diff_percentage=round(diff_percentage, 4),
            diff_pixel_count=diff_count,
            total_pixel_count=total_pixels,
            diff_image=diff_image,
        )


class LayoutMatchLevel(MatchLevelStrategy):
    """Layout Match Level - 布局对比。

    将图像划分为网格区域，比较区域的位置与尺寸特征，忽略区域内的像素细节。
    适合响应式布局验证，抗字体渲染、图片懒加载等噪声。

    算法：
        1. 将图像转为灰度
        2. 划分为 grid_size × grid_size 的网格
        3. 计算每个网格的平均亮度
        4. 比较对应网格的亮度差异，超过阈值的网格计入差异
    """

    def __init__(self, grid_size: int = 16, brightness_threshold: int = 15) -> None:
        """初始化 Layout 策略。

        Args:
            grid_size: 网格划分数（如 16 表示 16×16=256 个区域）
            brightness_threshold: 网格亮度差异阈值（0-255）
        """
        self._grid_size = grid_size
        self._brightness_threshold = brightness_threshold

    def compare(self, baseline: Image.Image, current: Image.Image) -> PixelDiffResult:
        """网格布局对比。"""
        width, height = self._ensure_same_size(baseline, current)
        total_pixels = width * height

        base_gray = np.array(baseline.convert("L"), dtype=np.int16)
        curr_gray = np.array(current.convert("L"), dtype=np.int16)

        # 计算网格平均亮度
        base_regions = self._compute_grid_averages(base_gray, width, height)
        curr_regions = self._compute_grid_averages(curr_gray, width, height)

        # 比较对应网格亮度
        region_diff = np.abs(base_regions - curr_regions)
        diff_regions = region_diff > self._brightness_threshold
        diff_count = int(diff_regions.sum())

        # 将差异网格映射回像素掩码用于生成差异图
        diff_mask = self._regions_to_pixel_mask(diff_regions, width, height)
        diff_percentage = (diff_count / (self._grid_size * self._grid_size) * 100.0)
        diff_image = self._generate_diff_image(baseline, current, diff_mask)

        return PixelDiffResult(
            diff_percentage=round(diff_percentage, 4),
            diff_pixel_count=diff_count,
            total_pixel_count=self._grid_size * self._grid_size,
            diff_image=diff_image,
        )

    def _compute_grid_averages(self, gray_arr: np.ndarray, width: int, height: int) -> np.ndarray:
        """计算 grid_size × grid_size 网格的平均亮度。"""
        cell_w = max(width // self._grid_size, 1)
        cell_h = max(height // self._grid_size, 1)
        averages = np.zeros((self._grid_size, self._grid_size), dtype=np.float32)
        for row in range(self._grid_size):
            for col in range(self._grid_size):
                y_start = row * cell_h
                y_end = min((row + 1) * cell_h, height)
                x_start = col * cell_w
                x_end = min((col + 1) * cell_w, width)
                if y_end > y_start and x_end > x_start:
                    averages[row, col] = float(gray_arr[y_start:y_end, x_start:x_end].mean())
        return averages

    def _regions_to_pixel_mask(self, diff_regions: np.ndarray, width: int, height: int) -> np.ndarray:
        """将差异网格映射为像素级掩码。"""
        cell_w = max(width // self._grid_size, 1)
        cell_h = max(height // self._grid_size, 1)
        mask = np.zeros((height, width), dtype=bool)
        for row in range(self._grid_size):
            for col in range(self._grid_size):
                if diff_regions[row, col]:
                    y_start = row * cell_h
                    y_end = min((row + 1) * cell_h, height)
                    x_start = col * cell_w
                    x_end = min((col + 1) * cell_w, width)
                    mask[y_start:y_end, x_start:x_end] = True
        return mask


class IgnoreColorsMatchLevel(MatchLevelStrategy):
    """Ignore Colors Match Level - 色彩忽略对比。

    先将图片转为灰度，再逐像素比较亮度差异。适合主题切换（深色/浅色模式）、
    品牌色变更等场景，只关注结构与亮度不变。
    """

    def __init__(self, brightness_threshold: int = 5) -> None:
        """初始化 IgnoreColors 策略。

        Args:
            brightness_threshold: 亮度差异阈值（0-255），默认 5 抗轻微渲染噪声
        """
        self._brightness_threshold = brightness_threshold

    def compare(self, baseline: Image.Image, current: Image.Image) -> PixelDiffResult:
        """灰度亮度对比。"""
        width, height = self._ensure_same_size(baseline, current)
        total_pixels = width * height

        base_gray = np.array(baseline.convert("L"), dtype=np.int16)
        curr_gray = np.array(current.convert("L"), dtype=np.int16)

        diff = np.abs(base_gray - curr_gray)
        diff_mask = diff > self._brightness_threshold
        diff_count = int(diff_mask.sum())

        diff_percentage = (diff_count / total_pixels * 100.0) if total_pixels > 0 else 0.0
        diff_image = self._generate_diff_image(baseline, current, diff_mask)

        return PixelDiffResult(
            diff_percentage=round(diff_percentage, 4),
            diff_pixel_count=diff_count,
            total_pixel_count=total_pixels,
            diff_image=diff_image,
        )


class MatchLevelFactory:
    """Match Level 工厂类，按 match_level 字符串返回策略实例。"""

    _strategies = {
        "strict": StrictMatchLevel,
        "layout": LayoutMatchLevel,
        "ignore_colors": IgnoreColorsMatchLevel,
    }

    @classmethod
    def create(cls, match_level: str) -> MatchLevelStrategy:
        """按 match_level 字符串创建策略实例。

        Args:
            match_level: 对比模式标识（strict/layout/ignore_colors）

        Returns:
            MatchLevelStrategy 实例

        Raises:
            ValueError: 未知 match_level 时抛出
        """
        strategy_cls = cls._strategies.get(match_level)
        if strategy_cls is None:
            raise ValueError(
                f"未知 Match Level: {match_level}，可选值: {list(cls._strategies.keys())}"
            )
        return strategy_cls()

    @classmethod
    def supported_levels(cls) -> list:
        """返回支持的 Match Level 列表。"""
        return list(cls._strategies.keys())


__all__ = [
    "PixelDiffResult",
    "MatchLevelStrategy",
    "StrictMatchLevel",
    "LayoutMatchLevel",
    "IgnoreColorsMatchLevel",
    "MatchLevelFactory",
]
