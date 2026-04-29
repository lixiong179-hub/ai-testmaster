"""
浏览器交互操作Mixin

提供页面元素交互能力，包括点击、输入、选择、等待等操作。
所有方法均使用require_initialized和handle_browser_errors装饰器，
确保浏览器已初始化且异常被统一捕获。

核心方法：
    - click: 点击指定坐标
    - click_element: 通过选择器点击元素
    - fill: 填充输入框
    - press_key: 按下键盘按键
    - wait_for_selector: 等待元素出现
    - get_all_input_elements: 获取页面所有输入元素
    - type_text: 逐字输入（模拟真人打字）
    - select_option: 选择下拉选项

依赖：
    - app.utils.browser_ctrl.types: 装饰器和异常类
"""
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger

from app.utils.browser_ctrl.types import (
    require_initialized, handle_browser_errors, ElementNotFoundError,
)


class InteractionMixin:
    """浏览器交互操作Mixin

    提供页面元素级别的交互操作，如点击、输入、选择等。
    与NavigationMixin（页面级操作）和MediaMixin（截图等）互补。

    所有公开方法均被以下装饰器包裹：
    - @handle_browser_errors: 捕获Playwright异常，转换为BrowserError
    - @require_initialized: 检查浏览器是否已初始化
    """

    @handle_browser_errors
    @require_initialized
    async def click(self, x: int, y: int) -> None:
        """点击页面指定坐标

        Args:
            x: 横坐标（像素）
            y: 纵坐标（像素）
        """
        await self._page.mouse.click(x, y)
        logger.debug(f"点击坐标: ({x}, {y})")

    @handle_browser_errors
    @require_initialized
    async def click_element(self, selector: str) -> None:
        """通过CSS选择器点击元素

        Args:
            selector: CSS选择器字符串

        Raises:
            ElementNotFoundError: 元素不存在或点击失败
        """
        try:
            await self._page.click(selector, timeout=5000)
            logger.debug(f"点击元素: {selector}")
        except Exception as e:
            raise ElementNotFoundError(f"点击元素失败: {selector}, 错误: {e}")

    @handle_browser_errors
    @require_initialized
    async def fill(self, selector: str, value: str) -> None:
        """填充输入框（清空后填入新值）

        Args:
            selector: CSS选择器字符串
            value: 要填入的值

        Raises:
            ElementNotFoundError: 元素不存在或填充失败
        """
        try:
            await self._page.fill(selector, value, timeout=5000)
            logger.debug(f"填充输入框: {selector} -> {value[:20]}...")
        except Exception as e:
            raise ElementNotFoundError(f"填充输入框失败: {selector}, 错误: {e}")

    @handle_browser_errors
    @require_initialized
    async def press_key(self, key: str) -> None:
        """按下键盘按键

        Args:
            key: 按键名称（如'Enter', 'Tab', 'Escape', 'Control+a'）
        """
        await self._page.keyboard.press(key)
        logger.debug(f"按下按键: {key}")

    @handle_browser_errors
    @require_initialized
    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """等待元素出现在页面中

        Args:
            selector: CSS选择器字符串
            timeout: 等待超时时间（毫秒），默认5000

        Returns:
            bool: 元素出现返回True，超时返回False
        """
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    @handle_browser_errors
    @require_initialized
    async def get_all_input_elements(self) -> List[Dict[str, Any]]:
        """获取页面中所有输入元素的信息

        通过JavaScript遍历页面中所有input、textarea、select元素，
        提取标签类型、名称、ID、占位符、位置和尺寸等信息。

        Returns:
            List[Dict[str, Any]]: 输入元素信息列表，每项包含：
                - tag: 标签名（input/textarea/select）
                - type: 输入类型（text/password/email等）
                - name: name属性
                - id: id属性
                - placeholder: 占位符文本
                - class: CSS类名
                - x/y/width/height: 位置和尺寸（像素）
        """
        js_code = """
        (function() {
            var inputs = document.querySelectorAll('input, textarea, select');
            var result = [];
            inputs.forEach(function(el) {
                var rect = el.getBoundingClientRect();
                result.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    name: el.getAttribute('name') || '',
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    class: el.className || '',
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                });
            });
            return result;
        })()
        """
        return await self._page.evaluate(js_code)

    @handle_browser_errors
    @require_initialized
    async def type_text(self, selector: str, text: str, delay: int = 50) -> None:
        """逐字输入文本（模拟真人打字）

        与fill不同，type_text不会清空已有内容，而是在当前光标位置逐字输入。
        适用于需要模拟真实用户输入行为的场景。

        Args:
            selector: CSS选择器字符串
            text: 要输入的文本
            delay: 每个字符间的延迟（毫秒），默认50ms
        """
        await self._page.type(selector, text, delay=delay)
        logger.debug(f"逐字输入: {selector}")

    @handle_browser_errors
    @require_initialized
    async def select_option(self, selector: str, value: str) -> None:
        """选择下拉框选项

        Args:
            selector: CSS选择器字符串（指向select元素）
            value: 选项值
        """
        await self._page.select_option(selector, value)
        logger.debug(f"选择选项: {selector} -> {value}")
