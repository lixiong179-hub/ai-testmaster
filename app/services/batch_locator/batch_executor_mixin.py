"""批量执行Mixin - 批量遍历步骤执行元素定位。
"""
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger

from app.models.test_case import TestStep
from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.utils.db_time import utcnow
from app.utils.browser_controller_v2 import BrowserControllerV2


class BatchExecutorMixin:

    async def _execute_prior_steps_cached(
        self,
        prior_steps: List[TestStep],
        browser: BrowserControllerV2,
        locator_cache: Dict[int, Optional[ElementLocator]]
    ) -> None:
        for prior_step in prior_steps:
            if prior_step.locator_status != LocatorStatus.RECORDED.value:
                continue
            if not prior_step.action_type:
                continue

            try:
                locator = locator_cache.get(prior_step.id)
                await self._execute_step_action(
                    browser, prior_step.action_type, locator,
                    input_value=prior_step.input_value,
                    target_element=prior_step.target_element
                )
            except Exception as e:
                logger.warning(f"执行前序步骤 {prior_step.id} 失败: {e}")

    async def _execute_step_action(
        self,
        browser: BrowserControllerV2,
        action_type: Optional[str],
        locator: Optional[ElementLocator],
        input_value: Optional[str] = None,
        target_element: Optional[str] = None
    ) -> None:
        if not action_type:
            return

        if action_type == "navigate":
            url = input_value or target_element
            if url:
                await browser.navigate(url)
                await asyncio.sleep(1)
        elif action_type == "click":
            if locator:
                if locator.css_selector:
                    try:
                        await browser.click_element(locator.css_selector)
                        await asyncio.sleep(0.5)
                        return
                    except Exception:
                        pass
                coord = locator.ai_coordinate if isinstance(locator.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await browser.click(x, y)
                    await asyncio.sleep(0.5)
        elif action_type == "input":
            value = input_value or ""
            if locator:
                if locator.css_selector:
                    try:
                        await browser.fill(locator.css_selector, value)
                        await asyncio.sleep(0.3)
                        return
                    except Exception:
                        pass
                coord = locator.ai_coordinate if isinstance(locator.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await browser.click(x, y)
                    await asyncio.sleep(0.3)
                    if value:
                        await browser.execute_javascript("""
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
                        """, value)
                        await asyncio.sleep(0.3)
        elif action_type == "hover":
            if locator:
                if locator.css_selector:
                    try:
                        safe_selector = locator.css_selector.replace("\\", "\\\\").replace("'", "\\'")
                        await browser.execute_javascript(f"""
                            var el = document.querySelector('{safe_selector}');
                            if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                        """)
                        await asyncio.sleep(0.5)
                        return
                    except Exception:
                        pass
                coord = locator.ai_coordinate if isinstance(locator.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await browser.execute_javascript(f"""
                        var el = document.elementFromPoint({x}, {y});
                        if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                    """)
                    await asyncio.sleep(0.5)
        elif action_type == "select":
            if locator:
                if locator.css_selector:
                    try:
                        await browser.click_element(locator.css_selector)
                        await asyncio.sleep(0.5)
                        if input_value:
                            safe_css = locator.css_selector.replace("\\", "\\\\").replace("'", "\\'")
                            await browser.execute_javascript(f"""
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
                            """, input_value)
                        return
                    except Exception:
                        pass
                coord = locator.ai_coordinate if isinstance(locator.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await browser.click(x, y)
                    await asyncio.sleep(0.5)
        elif action_type == "wait":
            await asyncio.sleep(2)
        elif action_type == "scroll":
            await browser.execute_javascript("window.scrollBy(0, 500)")
            await asyncio.sleep(0.5)

    def _is_high_quality_locator(self, locator: ElementLocator) -> bool:
        if locator.css_selector and locator.css_selector.strip():
            return True
        if locator.ai_confidence and locator.ai_confidence >= self.config.low_quality_threshold:
            return True
        return False

    def _notify_progress(self, data: Dict[str, Any]) -> None:
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
