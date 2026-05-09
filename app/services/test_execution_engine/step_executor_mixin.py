"""步骤执行Mixin - 处理单个测试步骤的执行逻辑。

包含核心的 _execute_step 方法，负责步骤的解析、定位、执行和结果记录。
"""
import json
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger

from app.models.test_case import TestStep
from app.models.element_locator import ElementLocator
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, ExecutionMode, StepExecutionError,
    StepExecutionResult,
)


class StepExecutorMixin:

    VALID_EXECUTION_MODES = {"preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"}

    async def _execute_step(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
        """执行单个测试步骤。"""
        if execution_mode not in self.VALID_EXECUTION_MODES:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到 'smart'")
            execution_mode = "smart"
        logger.info(f"执行步骤 {step.step_number}: {step.action[:50]}...")

        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )

        try:
            step_test_data, action_with_data = self._prepare_step_data(step)
            if step_test_data:
                result.execution_detail = json.dumps(step_test_data, ensure_ascii=False)

            action_type, action_info = self._resolve_action_type(step, action_with_data)

            if action_type == ActionType.INPUT and hasattr(step, 'input_value') and step.input_value:
                action_info["input_value"] = step.input_value

            locator_record, element_info, direct_executed = await self._resolve_locator(
                step, action_type, action_with_data, execution_mode
            )
            if locator_record:
                result.element_locator = locator_record.get_best_locator()

            is_mobile_mode = execution_mode in (ExecutionMode.MOBILE_REALTIME.value, ExecutionMode.MOBILE_SMART.value)
            if is_mobile_mode:
                await self._execute_mobile_step(step, action_with_data, execution_mode, result)
                return self._finalize_step_result(result, start_time)

            if execution_mode == ExecutionMode.PREPROCESS.value:
                if (
                    action_type in (
                        ActionType.INPUT, ActionType.CLICK,
                        ActionType.HOVER, ActionType.SELECT
                    )
                    and not locator_record
                ):
                    raise StepExecutionError(f"步骤 {step.step_number} 缺少元素定位信息，请先批量补充")

            await self._dispatch_step_action(
                step, action_type, action_info, step_test_data,
                locator_record, element_info, direct_executed
            )

            before_screenshot = None
            after_screenshot = None
            if self.browser and self.enable_ai_recognition:
                before_screenshot = await self.browser.take_screenshot()

            await asyncio.sleep(2)

            if self.browser:
                after_screenshot = await self.browser.take_screenshot()
                result.screenshot = after_screenshot

            if (before_screenshot and after_screenshot and
                self.enable_ai_recognition and step.expected_result):
                is_passed = await self.verify_execution_result(
                    before_screenshot, after_screenshot, action_with_data, step.expected_result
                )
                if not is_passed:
                    logger.warning(f"步骤 {step.step_number}: AI验证不通过")

            result.status = ExecutionStatus.PASSED
            result.ai_analysis = f"执行动作: {action_with_data}"
            logger.info(f"步骤 {step.step_number} 执行成功")

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception as e:
                    logger.debug(f"失败截图捕获异常(不影响结果): {e}")
            logger.error(f"步骤 {step.step_number} 执行失败: {str(e)}")

        return self._finalize_step_result(result, start_time)

    def _prepare_step_data(self, step: TestStep) -> tuple:
        """准备步骤测试数据和替换后的操作描述。"""
        step_test_data = {}
        action_with_data = step.action

        if self.enable_test_data_param:
            step_test_data = self._generate_step_test_data(step.id, self.parameterizer)
            if step_test_data:
                logger.info(f"步骤 {step.step_number}: 生成的测试数据: {step_test_data}")
                action_with_data = self._substitute_parameters_in_action(step.action, step_test_data)
                if action_with_data != step.action:
                    logger.info(f"步骤 {step.step_number}: 替换后操作: {action_with_data}")

        return step_test_data, action_with_data

    def _resolve_action_type(self, step: TestStep, action_with_data: str) -> tuple:
        """解析步骤的动作类型。"""
        if hasattr(step, 'action_type') and step.action_type:
            action_type_str = step.action_type.lower()
            action_type_map = {
                "click": ActionType.CLICK, "input": ActionType.INPUT,
                "navigate": ActionType.NAVIGATE, "verify": ActionType.VERIFY,
                "wait": ActionType.WAIT, "scroll": ActionType.SCROLL,
                "hover": ActionType.HOVER, "select": ActionType.SELECT,
                "captcha": ActionType.CAPTCHA, "refresh": ActionType.REFRESH,
                "keypress": ActionType.KEYPRESS,
            }
            action_type = action_type_map.get(action_type_str, ActionType.CLICK)
            action_info = {"type": action_type, "text": action_with_data}
        else:
            action_info = self._parse_step_action(action_with_data)
            action_type = action_info.get("type", ActionType.CLICK)
        return action_type, action_info

    async def _resolve_locator(
        self, step: TestStep, action_type: ActionType,
        action_with_data: str, execution_mode: str
    ) -> tuple:
        """解析步骤的元素定位器。"""
        locator_record = None
        element_info = None
        direct_executed = False

        if self.locator_service and step.id:
            locator_record = self.locator_service.get_locator(step.id)

        if execution_mode in (ExecutionMode.REALTIME.value, ExecutionMode.SMART.value):
            if not locator_record and self.locator_service and self.browser:
                logger.info(f"步骤 {step.step_number}: 无预存定位，尝试AI实时识别 (mode={execution_mode})")
                try:
                    page_title = await self._get_current_page_title()
                    element_info = await self.locator_service.smart_locate_element(
                        action_description=action_with_data,
                        page_title=page_title,
                        action_type=action_type.value if isinstance(action_type, ActionType) else action_type,
                        input_value=None
                    )
                    if element_info:
                        direct_executed = element_info.pop("_direct_executed", False)
                        locator_record = await self._save_realtime_locator(step, element_info)
                        if locator_record and not direct_executed:
                            logger.info(f"步骤 {step.step_number}: AI实时识别成功，已缓存定位信息")
                    else:
                        if execution_mode == ExecutionMode.REALTIME.value:
                            logger.warning(f"步骤 {step.step_number}: AI实时识别失败")
                except Exception as e:
                    logger.warning(f"步骤 {step.step_number}: AI实时识别异常: {e}")

        return locator_record, element_info, direct_executed

    async def _dispatch_step_action(
        self, step, action_type: ActionType, action_info: Dict[str, Any],
        step_test_data: Dict[str, str], locator_record, element_info, direct_executed: bool
    ) -> None:
        """分发步骤动作到对应的执行方法。"""
        if action_type == ActionType.NAVIGATE:
            await self._execute_navigate(action_info)
        elif action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT):
            if element_info and direct_executed:
                pass
            elif locator_record:
                await self._execute_with_self_healing(step, locator_record, action_type, action_info, step_test_data)
            else:
                await self._execute_action_by_type(action_type, action_info, step, step_test_data)
        elif action_type == ActionType.VERIFY:
            await self._execute_verify(action_info, step.id)
        elif action_type == ActionType.WAIT:
            await self._execute_wait(action_info)
        elif action_type == ActionType.SCROLL:
            await self._execute_scroll(action_info)
        elif action_type == ActionType.CAPTCHA:
            await self._execute_captcha(action_info, step.id)
        elif action_type == ActionType.REFRESH:
            await self._execute_refresh(action_info)
        elif action_type == ActionType.KEYPRESS:
            await self._execute_keypress(action_info)
        else:
            await self._execute_click(action_info, step.id, step_test_data)

    def _finalize_step_result(self, result: StepExecutionResult, start_time) -> StepExecutionResult:
        """完成步骤结果的时间记录。"""
        end_time = utcnow()
        duration = int((end_time - start_time).total_seconds() * 1000)
        result.end_time = end_time
        result.duration_ms = duration
        return result
