"""
步骤执行重试机制单元测试

覆盖场景：
    - 成功执行不重试
    - StepExecutionError 可重试
    - VerificationError 可重试
    - 不可恢复错误不重试
    - 重试成功记录 retry_count
    - 全部重试失败使用最后一次错误
    - retry_count 字段默认值
    - to_dict 包含 retry_count
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.test_case import TestStep
from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, StepExecutionError,
    VerificationError, StepExecutionResult,
)
from app.services.test_execution_engine.step_executor_mixin import (
    StepExecutorMixin, _UNRECOVERABLE_ERROR_PATTERNS,
)


class _StubEngine(StepExecutorMixin):
    """用于测试的最小引擎桩，仅提供 _execute_step 所需的属性和方法。"""

    def __init__(self) -> None:
        self.browser = None
        self.enable_ai_recognition = False
        self.enable_test_data_param = False
        self.parameterizer = None
        self.locator_service = None

    async def verify_execution_result(self, *args, **kwargs) -> bool:
        return True


def _make_step(step_number: int = 1, action: str = "点击登录按钮") -> TestStep:
    step = MagicMock(spec=TestStep)
    step.step_number = step_number
    step.action = action
    step.action_type = "click"
    step.input_value = None
    step.id = 100 + step_number
    step.expected_result = None
    step.target_element = None
    return step


class TestIsRetryableError:
    """_is_retryable_error 判断逻辑测试"""

    def test_step_execution_error_is_retryable(self) -> None:
        err = StepExecutionError("元素点击超时")
        assert StepExecutorMixin._is_retryable_error(err) is True

    def test_verification_error_is_retryable(self) -> None:
        err = VerificationError("验证不通过")
        assert StepExecutorMixin._is_retryable_error(err) is True

    def test_browser_not_initialized_not_retryable(self) -> None:
        err = StepExecutionError("浏览器未初始化，无法执行操作")
        assert StepExecutorMixin._is_retryable_error(err) is False

    def test_page_not_initialized_not_retryable(self) -> None:
        err = StepExecutionError("页面未初始化")
        assert StepExecutorMixin._is_retryable_error(err) is False

    def test_unrecoverable_patterns_constant(self) -> None:
        assert "浏览器未初始化" in _UNRECOVERABLE_ERROR_PATTERNS
        assert "页面未初始化" in _UNRECOVERABLE_ERROR_PATTERNS


class TestStepRetrySuccessPath:
    """成功执行路径不重试"""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.PASSED
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        call_count = 0
        original_dispatch = engine._dispatch_step_action

        async def flaky_dispatch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise StepExecutionError("元素暂时不可点击")

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", side_effect=flaky_dispatch), \
             patch.object(engine, "RETRY_DELAY", 0.0):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.PASSED
        assert result.retry_count == 1

    @pytest.mark.asyncio
    async def test_verification_error_retry_success(self) -> None:
        engine = _StubEngine()
        engine.enable_ai_recognition = True
        engine.browser = MagicMock()
        engine.browser.take_screenshot = AsyncMock(return_value=b"png")
        step = _make_step()
        step.expected_result = "页面显示成功"

        verify_call_count = 0

        async def flaky_verify(*args, **kwargs):
            nonlocal verify_call_count
            verify_call_count += 1
            return verify_call_count > 1

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock), \
             patch.object(engine, "verify_execution_result", side_effect=flaky_verify), \
             patch("app.services.test_execution_engine.step_executor_mixin.asyncio.sleep", new_callable=AsyncMock), \
             patch.object(engine, "RETRY_DELAY", 0.0):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.PASSED
        assert result.retry_count == 1


class TestStepRetryAllFailed:
    """全部重试失败路径"""

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock, side_effect=StepExecutionError("元素始终不可点击")), \
             patch.object(engine, "RETRY_DELAY", 0.0):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.FAILED
        assert "元素始终不可点击" in result.error_message
        assert result.retry_count == 2

    @pytest.mark.asyncio
    async def test_unrecoverable_error_no_retry(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock, side_effect=StepExecutionError("浏览器未初始化，无法执行操作")):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.FAILED
        assert result.retry_count == 0
        assert "浏览器未初始化" in result.error_message

    @pytest.mark.asyncio
    async def test_page_not_initialized_no_retry(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock, side_effect=StepExecutionError("页面未初始化")):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.FAILED
        assert result.retry_count == 0


class TestStepRetryNonRetryableException:
    """非 StepExecutionError/VerificationError 的普通异常不重试"""

    @pytest.mark.asyncio
    async def test_generic_exception_no_retry(self) -> None:
        engine = _StubEngine()
        step = _make_step()

        with patch.object(engine, "_prepare_step_data", return_value=({}, step.action)), \
             patch.object(engine, "_resolve_action_type", return_value=(ActionType.CLICK, {"type": ActionType.CLICK, "text": step.action})), \
             patch.object(engine, "_resolve_locator", return_value=(None, None, False)), \
             patch.object(engine, "_dispatch_step_action", new_callable=AsyncMock, side_effect=RuntimeError("意外错误")):
            result = await engine._execute_step(step)

        assert result.status == ExecutionStatus.FAILED
        assert result.retry_count == 0
        assert "意外错误" in result.error_message


class TestStepExecutionResultRetryCount:
    """StepExecutionResult retry_count 字段测试"""

    def test_default_retry_count_is_zero(self) -> None:
        result = StepExecutionResult(
            step_number=1,
            action_type=ActionType.CLICK,
        )
        assert result.retry_count == 0

    def test_retry_count_in_to_dict(self) -> None:
        result = StepExecutionResult(
            step_number=1,
            action_type=ActionType.CLICK,
            retry_count=2,
        )
        d = result.to_dict()
        assert d["retry_count"] == 2

    def test_retry_count_zero_in_to_dict(self) -> None:
        result = StepExecutionResult(
            step_number=1,
            action_type=ActionType.CLICK,
        )
        d = result.to_dict()
        assert d["retry_count"] == 0
