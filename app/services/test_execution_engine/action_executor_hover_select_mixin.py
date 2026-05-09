"""悬停选择动作执行Mixin - 处理鼠标悬停、下拉选择和滚动操作。
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import StepExecutionError


class ActionExecutorHoverSelectMixin:

    async def _execute_hover(
        self,
        action_info: Dict[str, Any],
        step_id: Optional[int],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text, step_test_data
                )
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            safe_selector = css_selector.replace(
                                "\\", "\\\\"
                            ).replace("'", "\\'")
                            await self.browser.execute_javascript("""
                                var el = document.querySelector(arguments[0]);
                                if (el) { el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); }
                            """, safe_selector)
                            logger.info(f"使用CSS选择器悬停: {css_selector}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器悬停失败: {e}")
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    if x < 0 or y < 0:
                        raise StepExecutionError(
                            f"AI识别坐标无效: ({x}, {y})，元素: {text}"
                        )
                    await self.browser.hover(x, y)
                    logger.info(f"悬停元素(坐标方式): ({x}, {y})")
                    return
            except Exception as e:
                logger.warning(f"智能定位悬停失败: {e}")
        selector = self._get_element_selector(text)
        if selector:
            try:
                safe_selector = selector.replace(
                    "\\", "\\\\"
                ).replace("'", "\\'")
                await self.browser.execute_javascript("""
                    var el = document.querySelector(arguments[0]);
                    if (el) { el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); }
                """, safe_selector)
                logger.info(f"使用预定义选择器悬停成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器悬停失败: {e}")
        logger.error(f"无法定位悬停元素: {text}")
        raise StepExecutionError(f"无法定位悬停元素: {text}")

    async def _execute_select(
        self,
        action_info: Dict[str, Any],
        step_id: Optional[int],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")
        text = action_info.get("text", "")
        select_value = action_info.get("input_value", "") or self._extract_input_text(text)
        if self.enable_ai_recognition or self.locator_service:
            try:
                element_info = await self.smart_locate_with_ai_fallback(
                    text, step_test_data
                )
                if element_info:
                    css_selector = element_info.get('css_selector')
                    if css_selector:
                        try:
                            await self.browser.click_element(css_selector)
                            await asyncio.sleep(0.5)
                            if select_value:
                                safe_css = css_selector.replace(
                                    "\\", "\\\\"
                                ).replace("'", "\\'")
                                await self.browser.execute_javascript("""
                                    var select = document.querySelector(arguments[0]);
                                    if (select && select.tagName === 'SELECT') {
                                        var options = select.options;
                                        for (var i = 0; i < options.length; i++) {
                                            if (options[i].text.includes(arguments[1]) || options[i].value === arguments[1]) {
                                                select.selectedIndex = i;
                                                select.dispatchEvent(new Event('change', {bubbles: true}));
                                                break;
                                            }
                                        }
                                    }
                                """, safe_css, select_value)
                            logger.info(f"使用CSS选择器选择: {css_selector} -> {select_value}")
                            return
                        except Exception as e:
                            logger.warning(f"CSS选择器选择失败: {e}")
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    if x < 0 or y < 0:
                        raise StepExecutionError(
                            f"AI识别坐标无效: ({x}, {y})，元素: {text}"
                        )
                    await self.browser.click(x, y)
                    await asyncio.sleep(0.5)
                    if select_value:
                        await self.browser.execute_javascript("""
                            var el = document.elementFromPoint(arguments[0], arguments[1]);
                            if (el && el.tagName === 'SELECT') {
                                var options = el.options;
                                for (var i = 0; i < options.length; i++) {
                                    if (options[i].text.includes(arguments[1]) || options[i].value === arguments[1]) {
                                        el.selectedIndex = i;
                                        el.dispatchEvent(new Event('change', {bubbles: true}));
                                        break;
                                    }
                                }
                            } else if (el) {
                                var selectParent = el.closest('select');
                                if (selectParent) {
                                    var opts = selectParent.options;
                                    for (var j = 0; j < opts.length; j++) {
                                        if (opts[j].text.includes(arguments[1]) || opts[j].value === arguments[1]) {
                                            selectParent.selectedIndex = j;
                                            selectParent.dispatchEvent(new Event('change', {bubbles: true}));
                                            break;
                                        }
                                    }
                                }
                            }
                        """, x, y, select_value)
                    logger.info(
                        f"点击选择元素(坐标方式): ({x}, {y})"
                        + (f" -> {select_value}" if select_value else "")
                    )
                    return
            except Exception as e:
                logger.warning(f"智能定位选择失败: {e}")
        selector = self._get_element_selector(text)
        if selector:
            try:
                await self.browser.click_element(selector)
                logger.info(f"使用预定义选择器选择成功: {selector}")
                return
            except Exception as e:
                logger.warning(f"预定义选择器选择失败: {e}")
        logger.error(f"无法定位选择元素: {text}")
        raise StepExecutionError(f"无法定位选择元素: {text}")
