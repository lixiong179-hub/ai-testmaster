"""步骤分派行为护栏（G-8 B4i：`_execute_single_step` 拆分前置测试）。

覆盖 5 类无定位动作直通、元素定位失败短路、click/input/hover/select 动作分派、
input 缺值时走通用动作、异常包装与结束时间/耗时兜底。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.test_execution_engine.models import (
    ActionType,
    ExecutionStatus,
    FailureCategory,
    StepExecutionError,
    StepExecutionResult,
)
from app.services.test_execution_engine.task_executor_mixin._executor import _ExecutorMixin


class _StepHarness(_ExecutorMixin):
    """最小宿主：记录各动作分派，不触达浏览器。"""

    def __init__(self, locator_service: Any = None) -> None:
        self.locator_service = locator_service
        self.browser = None
        self.calls: list[tuple] = []

    async def _execute_navigate(self, action_info):
        self.calls.append(("navigate", action_info))

    async def _execute_wait(self, action_info):
        self.calls.append(("wait", action_info))

    async def _execute_scroll(self, action_info):
        self.calls.append(("scroll", action_info))

    async def _execute_verify(self, action_info):
        self.calls.append(("verify", action_info))

    async def _execute_refresh(self, action_info):
        self.calls.append(("refresh", action_info))

    async def _execute_click_action(self, element_info, action_type):
        self.calls.append(("click", element_info, action_type))

    async def _execute_input_action(self, element_info, input_value):
        self.calls.append(("input", element_info, input_value))

    async def _execute_hover_action(self, element_info):
        self.calls.append(("hover", element_info))

    async def _execute_select_action(self, element_info, input_value):
        self.calls.append(("select", element_info, input_value))

    async def _execute_generic_action(self, action, element_info, step_data):
        self.calls.append(("generic", action, element_info, step_data))


def _make_step_result() -> StepExecutionResult:
    return StepExecutionResult(step_number=1, action_type=ActionType.CLICK, description="测试步骤")


def _locator_service(element_info: Any) -> MagicMock:
    service = MagicMock()
    service.locate_element = AsyncMock(return_value=element_info)
    return service


class TestExecuteSingleStep:
    async def test_without_locator_service_is_passed(self):
        engine = _StepHarness(locator_service=None)

        result = await engine._execute_single_step({"action": "点击按钮"}, ActionType.CLICK, _make_step_result())

        assert result.status == ExecutionStatus.PASSED
        assert engine.calls == []

    @pytest.mark.parametrize(
        ("action_type", "expected"),
        [
            ("navigate", "navigate"),
            ("wait", "wait"),
            ("scroll", "scroll"),
            ("verify", "verify"),
            ("refresh", "refresh"),
        ],
    )
    async def test_stateless_actions_dispatch_directly(self, action_type, expected):
        engine = _StepHarness(locator_service=MagicMock())

        result = await engine._execute_single_step(
            {"action": "动作", "expected_result": "预期"},
            ActionType(action_type),
            _make_step_result(),
        )

        assert result.status == ExecutionStatus.PASSED
        assert engine.calls[0][0] == expected

    async def test_verify_carries_expected_result(self):
        engine = _StepHarness(locator_service=MagicMock())

        await engine._execute_single_step(
            {"action": "校验文案", "expected_result": "显示成功"},
            ActionType.VERIFY,
            _make_step_result(),
        )

        assert engine.calls[0][1]["expected_result"] == "显示成功"

    async def test_locator_failure_short_circuits(self):
        engine = _StepHarness(locator_service=_locator_service(None))

        result = await engine._execute_single_step({"action": "点击登录"}, ActionType.CLICK, _make_step_result())

        assert result.status == ExecutionStatus.FAILED
        assert result.error_message == "元素定位失败: 点击登录"
        assert result.failure_category == FailureCategory.LOCATOR_FAILURE
        assert engine.calls == []

    async def test_click_dispatch_sets_element_info(self):
        element_info = {"css_selector": "#login"}
        engine = _StepHarness(locator_service=_locator_service(element_info))

        result = await engine._execute_single_step({"action": "点击登录"}, ActionType.CLICK, _make_step_result())

        assert result.status == ExecutionStatus.PASSED
        assert result.element_info == element_info
        assert engine.calls == [("click", element_info, ActionType.CLICK)]

    @pytest.mark.parametrize(("action_type", "expected"), [("hover", "hover"), ("select", "select")])
    async def test_hover_and_select_dispatch(self, action_type, expected):
        element_info = {"css_selector": "#city"}
        engine = _StepHarness(locator_service=_locator_service(element_info))

        await engine._execute_single_step(
            {"action": "悬停城市", "input_value": "上海"},
            ActionType(action_type),
            _make_step_result(),
        )

        assert engine.calls[0][0] == expected

    async def test_input_with_value_dispatch(self):
        element_info = {"css_selector": "#username"}
        engine = _StepHarness(locator_service=_locator_service(element_info))

        await engine._execute_single_step(
            {"action": "输入用户名", "input_value": "alice"},
            ActionType.INPUT,
            _make_step_result(),
        )

        assert engine.calls == [("input", element_info, "alice")]

    async def test_input_without_value_falls_to_generic(self):
        element_info = {"css_selector": "#username"}
        engine = _StepHarness(locator_service=_locator_service(element_info))

        await engine._execute_single_step({"action": "输入用户名"}, ActionType.INPUT, _make_step_result())

        assert engine.calls[0][0] == "generic"

    async def test_unknown_action_type_falls_to_generic(self):
        element_info = {"css_selector": "#panel"}
        engine = _StepHarness(locator_service=_locator_service(element_info))

        await engine._execute_single_step({"action": "展开面板"}, ActionType.DRAG_AND_DROP, _make_step_result())

        assert engine.calls[0][0] == "generic"

    async def test_action_exception_wrapped_and_timed(self):
        engine = _StepHarness(locator_service=MagicMock())

        async def _boom(action_info):
            raise RuntimeError("导航崩了")

        engine._execute_navigate = _boom
        step_result = _make_step_result()

        with pytest.raises(StepExecutionError, match="导航崩了"):
            await engine._execute_single_step({"action": "打开首页"}, ActionType.NAVIGATE, step_result)

        assert step_result.status == ExecutionStatus.FAILED
        assert step_result.error_message == "导航崩了"
        assert step_result.start_time is not None
        assert step_result.end_time is not None
