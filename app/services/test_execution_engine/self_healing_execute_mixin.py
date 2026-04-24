"""自愈执行Mixin - 在步骤执行中集成自愈修复逻辑。

当元素定位失败时，自动触发AI自愈机制，尝试通过多种策略
重新定位元素并执行操作，成功后回写新定位器到数据库。

自愈流程:
    1. 使用已有定位器尝试执行操作
    2. 捕获定位相关异常（超时、元素不存在等）
    3. 若自愈开关开启，使用AI自愈重试
    4. 自愈成功后回写新定位器到数据库（含乐观锁）
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger
from sqlalchemy import text as sql_text

from app.models.element_locator import ElementLocator
from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, StepExecutionError,
)


class SelfHealingExecuteMixin:

    async def _execute_with_self_healing(
        self,
        step,
        locator_record: Optional[ElementLocator],
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """带自愈兜底的步骤执行包装器。

        流程:
        1. 尝试使用 locator_record 的选择器执行操作
        2. 捕获 Playwright 超时/元素不存在异常
        3. 若自愈开关开启，使用AI自愈重试
        4. 自愈成功后回写新定位器到数据库

        Args:
            step: 测试步骤对象
            locator_record: 元素定位记录（可为None）
            action_type: 操作类型
            action_info: 操作信息字典
            step_test_data: 测试数据
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        old_selector = None
        if locator_record:
            best = locator_record.get_best_locator()
            if best:
                old_selector = best.get("value")

        try:
            await self._execute_action_directly(action_type, action_info, locator_record, step_test_data)
            if locator_record and old_selector:
                ElementLocator.atomic_record_success(self.db, locator_record.id, locator_record.version)
            return
        except Exception as primary_error:
            error_str = str(primary_error).lower()
            is_locator_error = any(kw in error_str for kw in [
                "timeout", "waiting", "not found", "no element",
                "selector", "等待", "超时", "未找到", "不存在",
                "stale", "detached", "not attached"
            ])

            if not is_locator_error:
                raise

            from app.core.config import settings
            if not settings.AI_SELF_HEALING_ENABLED:
                logger.info(f"定位器失效但自愈开关已关闭 | 旧选择器: {old_selector}")
                raise

            nl_description = await self._get_nl_description(step.id)
            if not nl_description:
                nl_description = action_info.get("text", "")

            self._self_healing_attempts += 1
            logger.info(
                f"定位器失效，启动AI自愈 | 旧选择器: {old_selector} | "
                f"步骤描述: {nl_description} | 步骤ID: {step.id}"
            )

            try:
                new_selector = await self._ai_self_heal_action(
                    nl_description, action_type, action_info, step_test_data
                )

                if new_selector and locator_record:
                    await self._update_locator_after_healing(
                        locator_record.id, new_selector, old_selector
                    )

                self._self_healing_successes += 1
                logger.info(f"自愈成功，新选择器已回写 | 新选择器: {new_selector}")
                return

            except Exception as heal_error:
                logger.error(
                    f"自愈失败，AI无法解析步骤 | 步骤描述: {nl_description} | "
                    f"自愈错误: {heal_error}"
                )
                raise primary_error

    async def _execute_action_directly(
        self,
        action_type: ActionType,
        action_info: Dict[str, Any],
        locator_record: Optional[ElementLocator],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """使用已有定位器直接执行操作（不含自愈逻辑）。

        Args:
            action_type: 操作类型
            action_info: 操作信息
            locator_record: 元素定位记录
            step_test_data: 测试数据
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        selector = None
        if locator_record:
            best = locator_record.get_best_locator()
            if best:
                loc_type = best.get("type")
                loc_value = best.get("value")

                if loc_type == "css":
                    selector = loc_value
                elif loc_type == "xpath":
                    selector = f"xpath={loc_value}"
                elif loc_type == "id":
                    selector = f"#{loc_value}"
                elif loc_type == "name":
                    selector = f"[name='{loc_value}']"
                elif loc_type == "ai" and isinstance(loc_value, dict):
                    x = loc_value.get("x", 0) + loc_value.get("width", 0) // 2
                    y = loc_value.get("y", 0) + loc_value.get("height", 0) // 2
                    if action_type == ActionType.INPUT:
                        input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
                        await self.browser.click(x, y)
                        await asyncio.sleep(0.3)
                        await self.browser.execute_javascript("""
                            (function() {
                                var el = document.activeElement;
                                if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                    nativeInputValueSetter.call(el, arguments[0]);
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            })()
                        """, input_text)
                        return
                    else:
                        await self.browser.click(x, y)
                        return

        if selector:
            if action_type == ActionType.INPUT:
                input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
                if step_test_data:
                    for field_name, value in step_test_data.items():
                        if field_name in action_info.get("text", "").lower():
                            input_text = value
                            break
                await self.browser.fill(selector, input_text)
                logger.info(f"使用选择器输入: {selector} -> {input_text}")
                return
            elif action_type == ActionType.CLICK:
                await self.browser.click_element(selector)
                logger.info(f"使用选择器点击: {selector}")
                return
            elif action_type == ActionType.HOVER:
                safe_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
                await self.browser.execute_javascript(f"""
                    var el = document.querySelector('{safe_selector}');
                    if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                """)
                return
            elif action_type == ActionType.SELECT:
                await self.browser.click_element(selector)
                return

        raise StepExecutionError(f"无法使用定位器执行操作: action_type={action_type}, selector={selector}")

    async def _execute_action_by_type(
        self,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step,
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """根据操作类型分发到对应的执行方法（不含自愈逻辑）。"""
        step_id = getattr(step, 'id', None)
        if action_type == ActionType.INPUT:
            await self._execute_input(action_info, step_id, step_test_data)
        elif action_type == ActionType.CLICK:
            await self._execute_click(action_info, step_id, step_test_data)
        elif action_type == ActionType.HOVER:
            await self._execute_hover(action_info, step_id, step_test_data)
        elif action_type == ActionType.SELECT:
            await self._execute_select(action_info, step_id, step_test_data)
        else:
            await self._execute_click(action_info, step_id, step_test_data)
