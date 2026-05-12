from typing import Optional, Dict, Any
from dataclasses import dataclass
from loguru import logger
import asyncio

from app.utils.browser_controller_base import (
    require_initialized,
    handle_browser_errors,
)


@dataclass
class ScreenshotConfig:
    full_page: bool = False
    clip: Optional[Dict[str, int]] = None
    type: str = "png"
    quality: Optional[int] = None

    def __post_init__(self) -> None:
        if self.type not in ("png", "jpeg"):
            raise ValueError(f"不支持的图片格式: {self.type}")
        if self.quality is not None and not (0 <= self.quality <= 100):
            raise ValueError(f"JPEG质量必须在0-100之间: {self.quality}")
        if self.clip is not None:
            required_keys = {"x", "y", "width", "height"}
            if not required_keys.issubset(self.clip.keys()):
                raise ValueError(f"裁剪区域必须包含: {required_keys}")
            for key in required_keys:
                if not isinstance(self.clip[key], int) or self.clip[key] < 0:
                    raise ValueError(f"{key}必须是非负整数")


class NavigationMixin:
    @require_initialized
    @handle_browser_errors
    async def navigate(self, url: str, wait_until: str = "networkidle") -> None:
        if not url or not url.startswith(("http://", "https://")):
            raise ValueError(f"无效的URL格式: {url}")
        logger.info(f"正在导航到: {url}")
        assert self._page is not None
        await self._page.goto(url, wait_until=wait_until)
        await asyncio.sleep(0.5)
        logger.info(f"页面加载完成: {url}")

    @require_initialized
    @handle_browser_errors
    async def take_screenshot(self, config: Optional[ScreenshotConfig] = None) -> bytes:
        config = config or ScreenshotConfig()
        screenshot_options: Dict[str, Any] = {"type": config.type}
        if config.full_page:
            screenshot_options["full_page"] = True
        if config.clip:
            screenshot_options["clip"] = config.clip
        if config.type == "jpeg" and config.quality is not None:
            screenshot_options["quality"] = config.quality
        assert self._page is not None
        screenshot_bytes = await self._page.screenshot(**screenshot_options)
        logger.info(f"截图成功，大小: {len(screenshot_bytes)} bytes")
        return screenshot_bytes

    @require_initialized
    @handle_browser_errors
    async def refresh(self) -> None:
        logger.info("正在刷新页面...")
        assert self._page is not None
        await self._page.reload(wait_until="networkidle")
        logger.info("页面刷新完成")
