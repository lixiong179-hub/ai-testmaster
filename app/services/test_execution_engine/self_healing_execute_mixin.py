"""自愈执行Mixin - 在步骤执行中集成自愈修复逻辑。
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from app.models.element_locator import ElementLocator
from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, StepExecutionError,
)


class SelfHealingExecuteMixin:

    async def _execute_with_self_healing(
        self,
        step,
        action_info: Dict[str, Any],
        original_error: Exception
    ) -> bool:
        logger.info(f"步骤 {step.step_number}: 启动自愈机制，原始错误: {original_error}")

        healing_strategies = [
            ("ai_vision", self._ai_self_heal_action),
            ("local_ai", self._local_ai_self_heal),
            ("stagehand", self._stagehand_self_heal),
        ]

        for strategy_name, strategy_func in healing_strategies:
            try:
                logger.info(f"步骤 {step.step_number}: 尝试自愈策略 - {strategy_name}")
                success = await strategy_func(step, action_info)
                if success:
                    logger.info(f"步骤 {step.step_number}: 自愈策略 {strategy_name} 成功")
                    self._self_healing_stats["total_healed"] += 1
                    self._self_healing_stats["healed_steps"].append({
                        "step_number": step.step_number,
                        "strategy": strategy_name,
                        "original_error": str(original_error),
                        "healed_at": self._get_current_datetime()
                    })
                    return True
            except Exception as e:
                logger.warning(f"步骤 {step.step_number}: 自愈策略 {strategy_name} 失败: {e}")
                continue

        logger.warning(f"步骤 {step.step_number}: 所有自愈策略均失败")
        return False

    def _get_current_datetime(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()

    async def _execute_action_directly(
        self,
        action_type: ActionType,
        action_info: Dict[str, Any],
        locator_record: ElementLocator,
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        if action_type == ActionType.NAVIGATE:
            await self._execute_navigate(action_info)
        elif action_type == ActionType.INPUT:
            input_value = action_info.get("input_value", "")
            if locator_record.css_selector:
                try:
                    await self.browser.fill(locator_record.css_selector, input_value)
                    return
                except Exception:
                    pass
            coord = locator_record.ai_coordinate if isinstance(locator_record.ai_coordinate, dict) else {}
            if coord:
                x = coord.get("x", 0) + coord.get("width", 0) // 2
                y = coord.get("y", 0) + coord.get("height", 0) // 2
                await self.browser.click(x, y)
                await asyncio.sleep(0.3)
                await self.browser.execute_javascript("""
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
                """, input_value)
        elif action_type == ActionType.CLICK:
            if locator_record.css_selector:
                try:
                    await self.browser.click_element(locator_record.css_selector)
                    return
                except Exception:
                    pass
            coord = locator_record.ai_coordinate if isinstance(locator_record.ai_coordinate, dict) else {}
            if coord:
                x = coord.get("x", 0) + coord.get("width", 0) // 2
                y = coord.get("y", 0) + coord.get("height", 0) // 2
                await self.browser.click(x, y)
        elif action_type == ActionType.HOVER:
            if locator_record.css_selector:
                safe_selector = locator_record.css_selector.replace("\\", "\\\\").replace("'", "\\'")
                await self.browser.execute_javascript(f"""
                    var el = document.querySelector('{safe_selector}');
                    if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                """)
            else:
                coord = locator_record.ai_coordinate if isinstance(locator_record.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await self.browser.execute_javascript(f"""
                        var el = document.elementFromPoint({x}, {y});
                        if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                    """)
        elif action_type == ActionType.SELECT:
            if locator_record.css_selector:
                await self.browser.click_element(locator_record.css_selector)
                await asyncio.sleep(0.5)
                input_value = action_info.get("input_value", "")
                if input_value:
                    safe_css = locator_record.css_selector.replace("\\", "\\\\").replace("'", "\\'")
                    await self.browser.execute_javascript(f"""
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
            else:
                coord = locator_record.ai_coordinate if isinstance(locator_record.ai_coordinate, dict) else {}
                if coord:
                    x = coord.get("x", 0) + coord.get("width", 0) // 2
                    y = coord.get("y", 0) + coord.get("height", 0) // 2
                    await self.browser.click(x, y)
        elif action_type == ActionType.WAIT:
            await asyncio.sleep(2)
        elif action_type == ActionType.SCROLL:
            await self.browser.execute_javascript("window.scrollBy(0, 500)")
        elif action_type == ActionType.VERIFY:
            await self._execute_verify(action_info, None)
        elif action_type == ActionType.CAPTCHA:
            await self._execute_captcha(action_info, None)
        elif action_type == ActionType.REFRESH:
            await self._execute_refresh(action_info)
        elif action_type == ActionType.KEYPRESS:
            await self._execute_keypress(action_info)

    async def _execute_action_by_type(self, action_type: ActionType, action_info: Dict[str, Any], step_id: Optional[int], step_test_data: Optional[Dict[str, str]] = None) -> None:
        if action_type == ActionType.NAVIGATE:
            await self._execute_navigate(action_info)
        elif action_type == ActionType.INPUT:
            await self._execute_input(action_info, step_id, step_test_data)
        elif action_type == ActionType.CLICK:
            await self._execute_click(action_info, step_id, step_test_data)
        elif action_type == ActionType.HOVER:
            await self._execute_hover(action_info, step_id, step_test_data)
        elif action_type == ActionType.SELECT:
            await self._execute_select(action_info, step_id, step_test_data)
        elif action_type == ActionType.VERIFY:
            await self._execute_verify(action_info, step_id)
        elif action_type == ActionType.WAIT:
            await self._execute_wait(action_info)
        elif action_type == ActionType.SCROLL:
            await self._execute_scroll(action_info)
        elif action_type == ActionType.CAPTCHA:
            await self._execute_captcha(action_info, step_id)
        elif action_type == ActionType.REFRESH:
            await self._execute_refresh(action_info)
        elif action_type == ActionType.KEYPRESS:
            await self._execute_keypress(action_info)
        else:
            raise StepExecutionError(f"不支持的动作类型: {action_type}")
