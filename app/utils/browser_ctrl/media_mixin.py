"""
浏览器媒体操作Mixin

提供截图、滚动、JavaScript执行等媒体相关操作。
截图支持全页截图、元素截图和自定义配置（格式、质量）。

核心方法：
    - take_screenshot: 截取页面或元素截图
    - save_screenshot: 截图并保存到文件
    - get_element_screenshot: 截取指定元素的截图
    - scroll_to: 滚动到指定坐标
    - execute_javascript: 执行JavaScript代码

依赖：
    - app.utils.browser_ctrl.types: 装饰器和配置类
"""
import os
import base64
from typing import Optional, Dict, Any, Union
from loguru import logger

from app.utils.browser_ctrl.types import (
    require_initialized, handle_browser_errors, ScreenshotConfig,
)


class MediaMixin:
    """浏览器媒体操作Mixin

    提供截图、滚动和JavaScript执行能力。
    截图支持全页/元素级别，以及PNG/JPEG格式和质量配置。
    """

    @handle_browser_errors
    @require_initialized
    async def take_screenshot(
        self,
        selector: Optional[str] = None,
        config: Optional[ScreenshotConfig] = None
    ) -> bytes:
        """截取页面或指定元素的截图

        当指定selector时截取对应元素，元素不存在时降级为全页截图。
        未指定selector时截取整个页面。

        Args:
            selector: CSS选择器，指定截取的元素，None时全页截图
            config: 截图配置（格式、质量、是否全页），None时使用默认配置

        Returns:
            bytes: 截图的字节数据（PNG或JPEG格式）
        """
        screenshot_config = config or ScreenshotConfig()
        kwargs = {
            "type": screenshot_config.type,
            "full_page": screenshot_config.full_page,
        }
        if screenshot_config.quality and screenshot_config.type == "jpeg":
            kwargs["quality"] = screenshot_config.quality

        if selector:
            element = await self._page.query_selector(selector)
            if element:
                screenshot_bytes = await element.screenshot(**kwargs)
            else:
                logger.warning(f"截图元素不存在: {selector}，改为全页截图")
                screenshot_bytes = await self._page.screenshot(**kwargs)
        else:
            screenshot_bytes = await self._page.screenshot(**kwargs)

        logger.debug(f"截图完成: {len(screenshot_bytes)} bytes")
        return screenshot_bytes

    @handle_browser_errors
    @require_initialized
    async def scroll_to(self, x: int = 0, y: int = 0) -> None:
        """滚动页面到指定坐标

        Args:
            x: 横向滚动位置（像素），默认0
            y: 纵向滚动位置（像素），默认0
        """
        await self._page.evaluate(f"window.scrollTo({x}, {y})")
        logger.debug(f"滚动到: ({x}, {y})")

    @handle_browser_errors
    @require_initialized
    async def execute_javascript(self, script: str, *args) -> Any:
        """在页面上下文中执行JavaScript代码

        Args:
            script: JavaScript代码字符串
            *args: 传递给脚本的参数

        Returns:
            Any: JavaScript执行的返回值
        """
        result = await self._page.evaluate(script, *args)
        return result

    @handle_browser_errors
    @require_initialized
    async def save_screenshot(self, filepath: str, config: Optional[ScreenshotConfig] = None) -> str:
        """截图并保存到文件

        自动创建目标目录，将截图字节数据写入文件。

        Args:
            filepath: 保存路径（绝对路径或相对路径）
            config: 截图配置，None时使用默认配置

        Returns:
            str: 保存的文件路径
        """
        screenshot_bytes = await self.take_screenshot(config=config)
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(screenshot_bytes)
        logger.info(f"截图已保存: {filepath}")
        return filepath

    @handle_browser_errors
    @require_initialized
    async def get_element_screenshot(self, selector: str) -> Optional[bytes]:
        """截取指定元素的截图

        Args:
            selector: CSS选择器字符串

        Returns:
            Optional[bytes]: 元素截图的PNG字节数据，元素不存在返回None
        """
        try:
            element = await self._page.query_selector(selector)
            if element:
                return await element.screenshot(type="png")
            return None
        except Exception as e:
            logger.warning(f"获取元素截图失败: {selector}, 错误: {e}")
            return None
