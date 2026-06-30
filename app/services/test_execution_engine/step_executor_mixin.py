"""步骤执行Mixin - 处理单个测试步骤的执行逻辑。

包含核心的 _execute_step / _execute_step_legacy 方法，负责步骤的解析、定位、
执行和结果记录，并在步骤执行前后集成浏览器缺陷捕获（控制台错误/网络失败/
内存泄漏/未捕获异常）。

浏览器缺陷捕获（_clear_browser_defect_evidence / _collect_step_defect_evidence）
拆分至 _step_defect_capture_mixin；辅助方法（_prepare_step_data /
_resolve_action_type / _resolve_locator / _dispatch_step_action /
_finalize_step_result）拆分至 _step_helpers_mixin。本模块保留核心执行流程
与重试控制。
"""
import json
import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger

from app.models.test_case import TestStep
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, StepExecutionError,
    VerificationError, StepExecutionResult,
)
from app.services.test_execution_engine._step_defect_capture_mixin import (
    StepDefectCaptureMixin,
)
from app.services.test_execution_engine._step_helpers_mixin import (
    StepHelpersMixin,
)


_UNRECOVERABLE_ERROR_PATTERNS = (
    "浏览器未初始化",
    "页面未初始化",
    "browser not initialized",
    "page not initialized",
)


class StepExecutorMixin(
    StepDefectCaptureMixin,
    StepHelpersMixin,
):
    """步骤执行聚合 Mixin。

    继承浏览器缺陷捕获子 Mixin 与辅助方法子 Mixin，本类保留
    _execute_step / _execute_step_legacy 核心执行流程与重试控制。
    """

    VALID_EXECUTION_MODES = {"preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"}
    MAX_STEP_RETRIES = 2
    RETRY_DELAY = 0.5

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        if not isinstance(error, (StepExecutionError, VerificationError)):
            return False
        message = str(error).lower()
        return not any(pattern.lower() in message for pattern in _UNRECOVERABLE_ERROR_PATTERNS)

    async def _execute_step_legacy(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
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

            is_mobile_mode = execution_mode in ("mobile_realtime", "mobile_smart")
            if is_mobile_mode:
                await self._execute_mobile_step(step, action_with_data, execution_mode, result)
                return self._finalize_step_result(result, start_time)

            if execution_mode == "preprocess":
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

    async def _execute_step(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
        """Execute a single test step with bounded retry for transient failures."""
        if execution_mode not in self.VALID_EXECUTION_MODES:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到 'smart'")
            execution_mode = "smart"

        # 步骤执行前清空缺陷收集器
        self._clear_browser_defect_evidence()

        start_time = utcnow()
        self._step_start_time_monotonic = time.monotonic()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
        )

        for attempt in range(self.MAX_STEP_RETRIES + 1):
            try:
                result.retry_count = attempt
                result.status = ExecutionStatus.RUNNING
                result.error_message = None

                step_test_data, action_with_data = self._prepare_step_data(step)
                if step_test_data:
                    result.execution_detail = json.dumps(step_test_data, ensure_ascii=False)

                action_type, action_info = self._resolve_action_type(step, action_with_data)
                result.action_type = action_type

                if action_type == ActionType.INPUT and hasattr(step, 'input_value') and step.input_value:
                    action_info["input_value"] = step.input_value

                locator_record, element_info, direct_executed = await self._resolve_locator(
                    step, action_type, action_with_data, execution_mode
                )
                if locator_record:
                    result.element_locator = locator_record.get_best_locator()

                is_mobile_mode = execution_mode in ("mobile_realtime", "mobile_smart")
                if is_mobile_mode:
                    await self._execute_mobile_step(step, action_with_data, execution_mode, result)
                    return self._finalize_step_result(result, start_time)

                if execution_mode == "preprocess":
                    if (
                        action_type in (
                            ActionType.INPUT,
                            ActionType.CLICK,
                            ActionType.HOVER,
                            ActionType.SELECT,
                        )
                        and not locator_record
                    ):
                        raise StepExecutionError(f"步骤 {step.step_number} 缺少元素定位信息，请先批量补全")

                before_screenshot = None
                if self.browser and self.enable_ai_recognition:
                    before_screenshot = await self.browser.take_screenshot()

                await self._dispatch_step_action(
                    step,
                    action_type,
                    action_info,
                    step_test_data,
                    locator_record,
                    element_info,
                    direct_executed,
                )

                await asyncio.sleep(2)

                after_screenshot = None
                if self.browser:
                    after_screenshot = await self.browser.take_screenshot()
                    result.screenshot = after_screenshot

                if (
                    before_screenshot
                    and after_screenshot
                    and self.enable_ai_recognition
                    and step.expected_result
                ):
                    is_passed = await self.verify_execution_result(
                        before_screenshot,
                        after_screenshot,
                        action_with_data,
                        step.expected_result,
                    )
                    if not is_passed:
                        raise VerificationError("验证不通过")

                result.status = ExecutionStatus.PASSED
                result.ai_analysis = f"执行动作: {action_with_data}"
                break
            except Exception as exc:
                result.status = ExecutionStatus.FAILED
                result.error_message = str(exc)

                if not self._is_retryable_error(exc) or attempt >= self.MAX_STEP_RETRIES:
                    if self.browser:
                        try:
                            result.screenshot = await self.browser.take_screenshot()
                        except Exception as screenshot_error:
                            logger.debug("失败截图捕获异常(不影响结果): {}", screenshot_error)
                    logger.error("步骤 {} 执行失败: {}", step.step_number, exc)
                    break

                logger.warning("步骤 {} 执行失败，准备重试: {}", step.step_number, exc)
                await asyncio.sleep(self.RETRY_DELAY)

        # 步骤完成后采集内存快照并收集缺陷证据
        await self._collect_step_defect_evidence(result)

        return self._finalize_step_result(result, start_time)
