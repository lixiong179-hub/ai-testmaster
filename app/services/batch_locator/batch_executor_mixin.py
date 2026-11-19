"""批量执行Mixin - 批量遍历步骤执行元素定位。"""

import asyncio
from typing import Any
from loguru import logger

from app.models.test_case import TestStep
from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.utils.browser_controller_v2 import BrowserControllerV2

_NATIVE_INPUT_JS = """
                            (function() {
                                var el = document.activeElement;
                                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                        window.HTMLInputElement.prototype, 'value'
                                    ).set;
                                    nativeInputValueSetter.call(el, arguments[0]);
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            })()
                        """


def _escape_js_string(value: str) -> str:
    """转义要嵌入单引号 JS 字符串的字符。"""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _locator_center(locator: ElementLocator | None) -> tuple[int, int] | None:
    """取 AI 坐标框中心点；无坐标时返回 None。"""
    if locator is None:
        return None
    coord = locator.ai_coordinate if isinstance(locator.ai_coordinate, dict) else {}
    if not coord:
        return None
    x = coord.get("x", 0) + coord.get("width", 0) // 2
    y = coord.get("y", 0) + coord.get("height", 0) // 2
    return x, y


class BatchExecutorMixin:
    async def _execute_prior_steps_cached(
        self, prior_steps: list[TestStep], browser: BrowserControllerV2, locator_cache: dict[int, ElementLocator | None]
    ) -> None:
        for prior_step in prior_steps:
            if prior_step.locator_status != LocatorStatus.RECORDED.value:
                continue
            if not prior_step.action_type:
                continue

            try:
                locator = locator_cache.get(prior_step.id)
                await self._execute_step_action(
                    browser,
                    prior_step.action_type,
                    locator,
                    input_value=prior_step.input_value,
                    target_element=prior_step.target_element,
                )
            except Exception as e:
                logger.warning(f"执行前序步骤 {prior_step.id} 失败: {e}")

    async def _execute_step_action(
        self,
        browser: BrowserControllerV2,
        action_type: str | None,
        locator: ElementLocator | None,
        input_value: str | None = None,
        target_element: str | None = None,
    ) -> None:
        if not action_type:
            return
        if action_type == "navigate":
            await self._step_navigate(browser, input_value, target_element)
        elif action_type == "click":
            await self._step_click(browser, locator)
        elif action_type == "input":
            await self._step_input(browser, locator, input_value)
        elif action_type == "hover":
            await self._step_hover(browser, locator)
        elif action_type == "select":
            await self._step_select(browser, locator, input_value)
        elif action_type == "wait":
            await asyncio.sleep(2)
        elif action_type == "scroll":
            await self._step_scroll(browser)

    async def _step_navigate(
        self, browser: BrowserControllerV2, input_value: str | None, target_element: str | None
    ) -> None:
        """跳转：input_value 优先，其次 target_element。"""
        url = input_value or target_element
        if url:
            await browser.navigate(url)
            await asyncio.sleep(1)

    async def _step_click(self, browser: BrowserControllerV2, locator: ElementLocator | None) -> None:
        """点击：CSS 选择器优先，失败或无选择器时按 AI 坐标中心点击。"""
        if not locator:
            return
        if locator.css_selector:
            try:
                await browser.click_element(locator.css_selector)
                await asyncio.sleep(0.5)
                return
            except Exception as e:
                logger.debug(f"CSS选择器点击失败，回退到坐标点击: {e}")
        center = _locator_center(locator)
        if center:
            await browser.click(*center)
            await asyncio.sleep(0.5)

    async def _step_input(
        self, browser: BrowserControllerV2, locator: ElementLocator | None, input_value: str | None
    ) -> None:
        """输入：CSS fill 优先，失败时坐标点击 + 原生 setter 注入。"""
        value = input_value or ""
        if not locator:
            return
        if locator.css_selector:
            try:
                await browser.fill(locator.css_selector, value)
                await asyncio.sleep(0.3)
                return
            except Exception:
                logger.debug("CSS选择器fill操作失败，降级为坐标输入", exc_info=True)
        center = _locator_center(locator)
        if not center:
            return
        await browser.click(*center)
        await asyncio.sleep(0.3)
        if value:
            await browser.execute_javascript(_NATIVE_INPUT_JS, value)
            await asyncio.sleep(0.3)

    async def _step_hover(self, browser: BrowserControllerV2, locator: ElementLocator | None) -> None:
        """悬停：CSS 触发 mouseover，失败时按坐标 elementFromPoint 触发。"""
        if not locator:
            return
        if locator.css_selector:
            try:
                safe_selector = _escape_js_string(locator.css_selector)
                await browser.execute_javascript(f"""
                            var el = document.querySelector('{safe_selector}');
                            if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                        """)
                await asyncio.sleep(0.5)
                return
            except Exception:
                logger.debug("CSS选择器hover操作失败，降级为坐标触发", exc_info=True)
        center = _locator_center(locator)
        if not center:
            return
        x, y = center
        await browser.execute_javascript(f"""
                        var el = document.elementFromPoint({x}, {y});
                        if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                    """)
        await asyncio.sleep(0.5)

    async def _step_select(
        self, browser: BrowserControllerV2, locator: ElementLocator | None, input_value: str | None
    ) -> None:
        """下拉选择：CSS 点击后按文本/值匹配 option，失败时坐标点击兜底。"""
        if not locator:
            return
        if locator.css_selector:
            try:
                await browser.click_element(locator.css_selector)
                await asyncio.sleep(0.5)
                if input_value:
                    safe_css = _escape_js_string(locator.css_selector)
                    await browser.execute_javascript(
                        f"""
                                var select = document.querySelector('{safe_css}');
                                if (select && select.tagName === 'SELECT') {{
                                    var options = select.options;
                                    for (var i = 0; i < options.length; i++) {{
                                        if (options[i].text.includes(arguments[0]) || options[i].value === arguments[0]) {{
                                            select.selectedIndex = i;
                                            select.dispatchEvent(new Event('change', {{bubbles: true}}));
                                            break;
                                        }}
                                    }}
                                }}
                            """,
                        input_value,
                    )
                return
            except Exception:
                logger.debug("CSS选择器select操作失败，降级为坐标点击", exc_info=True)
        center = _locator_center(locator)
        if center:
            await browser.click(*center)
            await asyncio.sleep(0.5)

    async def _step_scroll(self, browser: BrowserControllerV2) -> None:
        """滚动 500px。"""
        await browser.execute_javascript("window.scrollBy(0, 500)")
        await asyncio.sleep(0.5)

    def _is_high_quality_locator(self, locator: ElementLocator) -> bool:
        has_css = bool(locator.css_selector and locator.css_selector.strip())
        has_confident_ai = bool(locator.ai_confidence and locator.ai_confidence >= self.config.low_quality_threshold)
        return has_css or has_confident_ai

    def _notify_progress(self, data: dict[str, Any]) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(data)
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")

    def cancel(self) -> None:
        self._cancelled = True
        logger.info("批量记录任务已标记为取消")

    def get_report(self) -> Any:
        return self._current_report
