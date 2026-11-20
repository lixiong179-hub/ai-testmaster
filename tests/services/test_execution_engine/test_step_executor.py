"""StepExecutorMixin 执行流程护栏（G-8 B4 拆分前置测试）。

覆盖 legacy 单次执行与带重试执行两条路径：状态流转、移动端分流、
preprocess 定位校验、AI 验证结果处理、重试与不可恢复错误。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.test_execution_engine.models import (
    ActionType,
    ExecutionStatus,
    StepExecutionError,
)
from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin

SLEEP_TARGET = "app.services.test_execution_engine.step_executor_mixin.asyncio.sleep"


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _step(expected_result: str = "") -> _Obj:
    return _Obj(step_number=1, action="点击按钮", input_value="", expected_result=expected_result)


class _Stub(StepExecutorMixin):
    """替换协作方法，只保留被测执行流程。"""

    def __init__(self, *, verify_result: bool = True, has_locator: bool = False) -> None:
        self.browser = MagicMock()
        self.browser.take_screenshot = AsyncMock(return_value="shot.png")
        self.enable_ai_recognition = True
        self.verify_result = verify_result
        self.has_locator = has_locator
        self.dispatched: list = []
        self.mobile_calls = 0
        self.dispatch_side_effects: list = []
        self.cleared = False
        self.collected = False

    def _prepare_step_data(self, step):
        return {"k": "v"}, "点击按钮"

    def _resolve_action_type(self, step, action_with_data):
        return ActionType.CLICK, {"text": action_with_data}

    async def _resolve_locator(self, step, action_type, action_with_data, execution_mode):
        locator_record = MagicMock()
        locator_record.get_best_locator.return_value = "css=#btn"
        return (locator_record if self.has_locator else None), "elem", False

    async def _execute_mobile_step(self, step, action_with_data, execution_mode, result):
        self.mobile_calls += 1
        result.status = ExecutionStatus.PASSED

    async def _dispatch_step_action(
        self, step, action_type, action_info, step_test_data, locator_record, element_info, direct_executed
    ):
        if self.dispatch_side_effects:
            effect = self.dispatch_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
        self.dispatched.append(action_type)

    async def verify_execution_result(self, before, after, action_with_data, expected):
        return self.verify_result

    def _finalize_step_result(self, result, start_time):
        return result

    def _clear_browser_defect_evidence(self) -> None:
        self.cleared = True

    async def _collect_step_defect_evidence(self, result) -> None:
        self.collected = True


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch(SLEEP_TARGET, new=AsyncMock()):
        yield


async def test_legacy_passes_and_captures_screenshot():
    stub = _Stub()
    result = await stub._execute_step_legacy(_step("期望结果"), "smart")

    assert result.status == ExecutionStatus.PASSED
    assert result.screenshot == "shot.png"
    assert stub.dispatched == [ActionType.CLICK]
    assert stub.collected is False


async def test_legacy_verify_failure_still_passes():
    stub = _Stub(verify_result=False)
    result = await stub._execute_step_legacy(_step("期望结果"), "smart")

    assert result.status == ExecutionStatus.PASSED


async def test_legacy_preprocess_requires_locator():
    stub = _Stub(has_locator=False)
    result = await stub._execute_step_legacy(_step(), "preprocess")

    assert result.status == ExecutionStatus.FAILED
    assert "请先批量补充" in result.error_message


async def test_legacy_mobile_mode_skips_dispatch():
    stub = _Stub()
    result = await stub._execute_step_legacy(_step(), "mobile_smart")

    assert stub.mobile_calls == 1
    assert stub.dispatched == []
    assert result.status == ExecutionStatus.PASSED


async def test_legacy_exception_marks_failed_with_screenshot():
    stub = _Stub()
    stub.dispatch_side_effects = [RuntimeError("boom")]
    result = await stub._execute_step_legacy(_step(), "smart")

    assert result.status == ExecutionStatus.FAILED
    assert result.error_message == "boom"
    assert result.screenshot == "shot.png"


async def test_legacy_invalid_mode_falls_back_to_smart():
    stub = _Stub()
    result = await stub._execute_step_legacy(_step(), "bogus")

    assert result.status == ExecutionStatus.PASSED
    assert stub.mobile_calls == 0


async def test_step_retries_transient_error_then_passes():
    stub = _Stub()
    stub.dispatch_side_effects = [StepExecutionError("元素尚未渲染")]
    result = await stub._execute_step(_step(), "smart")

    assert result.status == ExecutionStatus.PASSED
    assert result.retry_count == 1
    assert stub.cleared is True
    assert stub.collected is True


async def test_step_unrecoverable_error_not_retried():
    stub = _Stub()
    stub.dispatch_side_effects = [StepExecutionError("浏览器未初始化")]
    result = await stub._execute_step(_step(), "smart")

    assert result.status == ExecutionStatus.FAILED
    assert result.retry_count == 0
    assert "浏览器未初始化" in result.error_message


async def test_step_verify_failure_exhausts_retries():
    stub = _Stub(verify_result=False)
    result = await stub._execute_step(_step("期望结果"), "smart")

    assert result.status == ExecutionStatus.FAILED
    assert result.error_message == "验证不通过"
    assert result.retry_count == stub.MAX_STEP_RETRIES


async def test_step_preprocess_requires_locator():
    stub = _Stub(has_locator=False)
    result = await stub._execute_step(_step(), "preprocess")

    assert result.status == ExecutionStatus.FAILED
    assert "请先批量补全" in result.error_message


async def test_step_mobile_mode_returns_without_dispatch():
    stub = _Stub()
    result = await stub._execute_step(_step(), "mobile_realtime")

    assert stub.mobile_calls == 1
    assert stub.dispatched == []
    assert result.status == ExecutionStatus.PASSED
