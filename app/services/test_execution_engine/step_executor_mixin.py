"""步骤执行Mixin - 处理单个测试步骤的执行逻辑。

包含核心的 _execute_step / _execute_step_legacy 方法，负责步骤的解析、定位、
执行和结果记录，并在步骤执行前后集成浏览器缺陷捕获（控制台错误/网络失败/
内存泄漏/未捕获异常）。

浏览器缺陷捕获（_clear_browser_defect_evidence / _collect_step_defect_evidence）
拆分至 _step_defect_capture_mixin；辅助方法（_prepare_step_data /
_resolve_action_type / _resolve_locator / _dispatch_step_action /
_finalize_step_result）拆分至 _step_helpers_mixin。本模块保留核心执行流程、
单次尝试准备/校验/截图等阶段方法与重试控制。
"""

import json
import asyncio
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.models.test_case import TestStep
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus,
    ActionType,
    StepExecutionError,
    VerificationError,
    StepExecutionResult,
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

# preprocess 模式下必须已有元素定位信息的动作类型
_LOCATOR_REQUIRED_ACTIONS = (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT)

_MOBILE_EXECUTION_MODES = ("mobile_realtime", "mobile_smart")


@dataclass
class _PreparedStep:
    """单次步骤尝试的解析结果。"""

    step_test_data: dict[str, Any]
    action_with_data: str
    action_type: ActionType
    action_info: dict[str, Any]
    locator_record: Any
    element_info: Any
    direct_executed: bool
    is_mobile: bool


class StepExecutorMixin(
    StepDefectCaptureMixin,
    StepHelpersMixin,
):
    """步骤执行聚合 Mixin。

    继承浏览器缺陷捕获子 Mixin 与辅助方法子 Mixin，本类保留
    _execute_step / _execute_step_legacy 核心执行流程与重试控制。
    """

    # 兼容新旧 ExecutionMode 值:
    # - 旧值 (legacy): preprocess/realtime/smart/mobile_realtime/mobile_smart (内部执行分支仍按这些值判断)
    # - 新值 (ExecutionMode 枚举): ai_vision/api/unknown (新版 API 契约)
    # 新值传入时不命中 preprocess/mobile_* 分支，按"智能视觉"默认路径执行，与 AI_VISION 语义一致
    VALID_EXECUTION_MODES = {
        "preprocess",
        "realtime",
        "smart",
        "mobile_realtime",
        "mobile_smart",
        "ai_vision",
        "api",
        "unknown",
    }
    MAX_STEP_RETRIES = 2
    RETRY_DELAY = 0.5

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        if not isinstance(error, (StepExecutionError, VerificationError)):
            return False
        message = str(error).lower()
        return not any(pattern.lower() in message for pattern in _UNRECOVERABLE_ERROR_PATTERNS)

    def _normalize_execution_mode(self, execution_mode: str) -> str:
        """非法模式回落 smart，避免下游分支全部不命中。"""
        if execution_mode in self.VALID_EXECUTION_MODES:
            return execution_mode
        logger.warning(f"非法执行模式 '{execution_mode}'，回退到 'smart'")
        return "smart"

    async def _prepare_step_execution(
        self, step: TestStep, execution_mode: str, result: StepExecutionResult
    ) -> _PreparedStep:
        """准备测试数据、动作类型、输入值、定位记录，并回写结果明细。"""
        step_test_data, action_with_data = self._prepare_step_data(step)
        if step_test_data:
            result.execution_detail = json.dumps(step_test_data, ensure_ascii=False)

        action_type, action_info = self._resolve_action_type(step, action_with_data)
        if action_type == ActionType.INPUT and getattr(step, "input_value", None):
            action_info["input_value"] = step.input_value

        locator_record, element_info, direct_executed = await self._resolve_locator(
            step, action_type, action_with_data, execution_mode
        )
        if locator_record:
            result.element_locator = locator_record.get_best_locator()

        return _PreparedStep(
            step_test_data=step_test_data,
            action_with_data=action_with_data,
            action_type=action_type,
            action_info=action_info,
            locator_record=locator_record,
            element_info=element_info,
            direct_executed=direct_executed,
            is_mobile=execution_mode in _MOBILE_EXECUTION_MODES,
        )

    def _ensure_preprocess_locator(
        self, step: TestStep, execution_mode: str, prepared: _PreparedStep, hint: str
    ) -> None:
        """preprocess 模式下交互动作缺少定位信息即失败。"""
        if execution_mode != "preprocess":
            return
        if prepared.action_type not in _LOCATOR_REQUIRED_ACTIONS:
            return
        if prepared.locator_record:
            return
        raise StepExecutionError(f"步骤 {step.step_number} 缺少元素定位信息，{hint}")

    async def _capture_before_screenshot(self) -> Any | None:
        if self.browser and self.enable_ai_recognition:
            return await self.browser.take_screenshot()
        return None

    async def _capture_after_screenshot(self, result: StepExecutionResult) -> Any | None:
        if not self.browser:
            return None
        screenshot = await self.browser.take_screenshot()
        result.screenshot = screenshot
        return screenshot

    async def _capture_failure_screenshot(self, result: StepExecutionResult) -> None:
        """失败兜底截图，异常不影响主结果。"""
        if not self.browser:
            return
        try:
            result.screenshot = await self.browser.take_screenshot()
        except Exception as e:
            logger.debug(f"失败截图捕获异常(不影响结果): {e}")

    async def _ai_verify(
        self, before_screenshot: Any, after_screenshot: Any, step: TestStep, action_with_data: str
    ) -> bool | None:
        """执行 AI 结果校验；不具备校验条件时返回 None。"""
        if not (before_screenshot and after_screenshot and self.enable_ai_recognition and step.expected_result):
            return None
        return await self.verify_execution_result(
            before_screenshot, after_screenshot, action_with_data, step.expected_result
        )

    async def _should_stop_retrying(
        self, exc: Exception, attempt: int, result: StepExecutionResult, step: TestStep
    ) -> bool:
        """不可恢复或已达上限则记录失败并停止重试。"""
        if self._is_retryable_error(exc) and attempt < self.MAX_STEP_RETRIES:
            logger.warning("步骤 {} 执行失败，准备重试: {}", step.step_number, exc)
            return False
        await self._capture_failure_screenshot(result)
        logger.error("步骤 {} 执行失败: {}", step.step_number, exc)
        return True

    async def _execute_step_legacy(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
        """执行单个测试步骤。"""
        execution_mode = self._normalize_execution_mode(execution_mode)
        logger.info(f"执行步骤 {step.step_number}: {step.action[:50]}...")

        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number, action=step.action, status=ExecutionStatus.RUNNING, start_time=start_time
        )

        try:
            prepared = await self._prepare_step_execution(step, execution_mode, result)

            if prepared.is_mobile:
                await self._execute_mobile_step(step, prepared.action_with_data, execution_mode, result)
                return self._finalize_step_result(result, start_time)

            self._ensure_preprocess_locator(step, execution_mode, prepared, "请先批量补充")

            await self._dispatch_step_action(
                step,
                prepared.action_type,
                prepared.action_info,
                prepared.step_test_data,
                prepared.locator_record,
                prepared.element_info,
                prepared.direct_executed,
            )

            before_screenshot = await self._capture_before_screenshot()
            await asyncio.sleep(2)
            after_screenshot = await self._capture_after_screenshot(result)

            if await self._ai_verify(before_screenshot, after_screenshot, step, prepared.action_with_data) is False:
                logger.warning(f"步骤 {step.step_number}: AI验证不通过")

            result.status = ExecutionStatus.PASSED
            result.ai_analysis = f"执行动作: {prepared.action_with_data}"
            logger.info(f"步骤 {step.step_number} 执行成功")

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            await self._capture_failure_screenshot(result)
            logger.error(f"步骤 {step.step_number} 执行失败: {str(e)}")

        return self._finalize_step_result(result, start_time)

    async def _execute_step(self, step: TestStep, execution_mode: str = "smart") -> StepExecutionResult:
        """Execute a single test step with bounded retry for transient failures."""
        execution_mode = self._normalize_execution_mode(execution_mode)

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

                prepared = await self._prepare_step_execution(step, execution_mode, result)
                result.action_type = prepared.action_type

                if prepared.is_mobile:
                    await self._execute_mobile_step(step, prepared.action_with_data, execution_mode, result)
                    return self._finalize_step_result(result, start_time)

                self._ensure_preprocess_locator(step, execution_mode, prepared, "请先批量补全")

                before_screenshot = await self._capture_before_screenshot()

                await self._dispatch_step_action(
                    step,
                    prepared.action_type,
                    prepared.action_info,
                    prepared.step_test_data,
                    prepared.locator_record,
                    prepared.element_info,
                    prepared.direct_executed,
                )

                await asyncio.sleep(2)

                after_screenshot = await self._capture_after_screenshot(result)

                if await self._ai_verify(before_screenshot, after_screenshot, step, prepared.action_with_data) is False:
                    raise VerificationError("验证不通过")

                result.status = ExecutionStatus.PASSED
                result.ai_analysis = f"执行动作: {prepared.action_with_data}"
                break
            except Exception as exc:
                result.status = ExecutionStatus.FAILED
                result.error_message = str(exc)
                if await self._should_stop_retrying(exc, attempt, result, step):
                    break
                await asyncio.sleep(self.RETRY_DELAY)

        # 步骤完成后采集内存快照并收集缺陷证据
        await self._collect_step_defect_evidence(result)

        return self._finalize_step_result(result, start_time)
