"""输入点击动作执行Mixin - 处理点击、双击、右键点击、输入和文件上传操作。
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import (
    StepExecutionError,
)


class ActionExecutorInputClickMixin:

    async def _execute_input(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        input_text = action_info.get("input_value", "") or self._extract_input_text(text)

        if step_test_data:
            for field_name, value in step_test_data.items():
                if field_name in text.lower() or field_name in action_info.get("text", ""):
                    input_text = value
                    logger.info(f"使用测试数据输入值: {field_name} = {value}")
                    break
            if input_text == "test" and step_test_data:
                input_text = list(step_test_data.values())[0]
                logger.info(f"使用测试数据第一个值: {input_text}")

        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(text, step_test_data)
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            await self.browser.fill(css_selector, input_text)
                            logger.info(f"使用CSS选择器输入: {css_selector} -> {input_text}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器输入失败: {e}")
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    if x < 0 or y < 0:
                        raise StepExecutionError(
                            f"AI识别坐标无效: ({x}, {y})，元素: {text}"
                        )
                    await self.browser.click(x, y)
                    await asyncio.sleep(0.3)
                    await self.browser.execute_javascript("""
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
                    """, input_text)
                    logger.info(f"输入文本(坐标方式): {input_text}")
                    return
            except Exception as e:
                logger.warning(f"智能定位输入失败: {e}")

        logger.error(f"无法定位输入元素: {text}")
        raise StepExecutionError(f"无法定位输入元素: {text}")

    async def _execute_click(self, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")

        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(text, step_test_data)
                if element_info:
                    css_selector = element_info.get('css_selector')
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
                        raise StepExecutionError(
                            f"AI识别坐标无效: ({x}, {y})，元素: {text}"
                        )
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
        matches = re.findall(r'[""'']([^""'']+)[""'']', text)
        if matches:
            return matches[-1]
        match = re.search(r'输入\s+(\S+)', text)
        if match:
            return match.group(1)
        match = re.search(r'填写\s+(\S+)', text)
        if match:
            return match.group(1)
        logger.warning(f"无法从文本中提取输入内容: {text}，使用默认值")
        return "test"
