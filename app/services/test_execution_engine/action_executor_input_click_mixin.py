"""输入点击动作执行Mixin - 处理点击、双击、右键点击、输入和文件上传操作。"""

import asyncio
from typing import Any
from loguru import logger

from app.services.test_execution_engine.models import (
    StepExecutionError,
)

# 坐标输入脚本：绕过 React/Vue 受控组件，用原生 setter 写值并派发 input/change
_NATIVE_INPUT_JS = """
                        (function() {
                            var el = document.activeElement;
                            if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                var desc = Object.getOwnPropertyDescriptor(
                                    window.HTMLInputElement.prototype, 'value'
                                );
                                desc.set.call(el, arguments[0]);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        })()
                    """


class ActionExecutorInputClickMixin:
    async def _execute_input(
        self, action_info: dict[str, Any], step_id: int | None, step_test_data: dict[str, str] | None = None
    ) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        input_text = self._resolve_input_text(text, action_info, step_test_data)

        if (self.enable_ai_recognition or self.locator_service) and await self._input_by_smart_locate(
            text, input_text, step_test_data
        ):
            return

        logger.error(f"无法定位输入元素: {text}")
        raise StepExecutionError(f"无法定位输入元素: {text}")

    def _resolve_input_text(self, text: str, action_info: dict[str, Any], step_test_data: dict[str, str] | None) -> str:
        """确定输入值：显式参数 > 文本提取 > 测试数据字段匹配 > 测试数据首个值。"""
        input_text = action_info.get("input_value", "") or self._extract_input_text(text)
        if not step_test_data:
            return input_text

        matched_field = next(
            (name for name in step_test_data if name in text.lower() or name in text),
            None,
        )
        if matched_field is not None:
            input_text = step_test_data[matched_field]
            logger.info(f"使用测试数据输入值: {matched_field} = {input_text}")
        if input_text == "test":
            input_text = list(step_test_data.values())[0]
            logger.info(f"使用测试数据第一个值: {input_text}")
        return input_text

    async def _input_by_smart_locate(self, text: str, input_text: str, step_test_data: dict[str, str] | None) -> bool:
        """智能定位输入：CSS 填充优先，失败降级坐标 + 原生 setter 注入。"""
        try:
            element_info = await self.smart_locate_with_ai_fallback(text, step_test_data)
            if not element_info:
                return False
            css_selector = element_info.get("css_selector")
            if css_selector and await self._input_by_css(css_selector, input_text):
                return True
            return await self._input_by_coordinate(element_info, input_text, text)
        except Exception as e:
            logger.warning(f"智能定位输入失败: {e}")
            return False

    async def _input_by_css(self, css_selector: str, input_text: str) -> bool:
        """CSS 选择器填充；失败返回 False 交由坐标方式兜底。"""
        try:
            await self.browser.fill(css_selector, input_text)
        except Exception as e:
            logger.warning(f"CSS选择器输入失败: {e}")
            return False
        logger.info(f"使用CSS选择器输入: {css_selector} -> {input_text}")
        return True

    async def _input_by_coordinate(self, element_info: dict[str, Any], input_text: str, text: str) -> bool:
        """坐标方式输入：点击后对 activeElement 用原生 setter 写值并派发事件。"""
        x = element_info.get("x", 0) + element_info.get("width", 0) // 2
        y = element_info.get("y", 0) + element_info.get("height", 0) // 2
        if x < 0 or y < 0:
            raise StepExecutionError(f"AI识别坐标无效: ({x}, {y})，元素: {text}")
        await self.browser.click(x, y)
        await asyncio.sleep(0.3)
        await self.browser.execute_javascript(_NATIVE_INPUT_JS, input_text)
        logger.info(f"输入文本(坐标方式): {input_text}")
        return True

    async def _execute_click(
        self, action_info: dict[str, Any], step_id: int | None, step_test_data: dict[str, str] | None = None
    ) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")

        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(text, step_test_data)
                if element_info:
                    css_selector = element_info.get("css_selector")
                    if css_selector:
                        try:
                            await self.browser.click_element(css_selector)
                            logger.info(f"使用CSS选择器点击: {css_selector}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器点击失败: {e}")
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    if x < 0 or y < 0:
                        raise StepExecutionError(f"AI识别坐标无效: ({x}, {y})，元素: {text}")
                    await self.browser.click(x, y)
                    logger.info(f"点击元素(坐标方式): ({x}, {y})")
                    return
            except Exception as e:
                logger.warning(f"智能定位点击失败: {e}")

        selector = self._get_element_selector(text)
        if selector:
            try:
                await self.browser.click_element(selector)
                logger.info(f"使用预定义选择器点击成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器点击失败: {e}")

        logger.error(f"无法定位点击元素: {text}")
        raise StepExecutionError(f"无法定位点击元素: {text}")

    def _extract_input_text(self, text: str) -> str:
        import re

        matches = re.findall(r'["\']([^"\']+)["\']', text)
        if matches:
            return matches[-1]
        matches = re.findall(r'[""' ']([^""' ']+)[""' "]", text)
        if matches:
            return matches[-1]
        match = re.search(r"输入\s+(\S+)", text)
        if match:
            return match.group(1)
        match = re.search(r"填写\s+(\S+)", text)
        if match:
            return match.group(1)
        logger.warning(f"无法从文本中提取输入内容: {text}，使用默认值")
        return "test"
