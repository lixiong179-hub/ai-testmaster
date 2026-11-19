"""BatchExecutorMixin._execute_step_action 行为护栏（G-8 B3i 拆分前置测试）。

覆盖 6 类动作的正常路径与 CSS 失败后的坐标/JS 回退路径。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.batch_locator.batch_executor_mixin import BatchExecutorMixin

SLEEP_TARGET = "app.services.batch_locator.batch_executor_mixin.asyncio.sleep"


class _Executor(BatchExecutorMixin):
    """空壳：被测方法不依赖其它实例状态。"""


def _locator(css_selector=None, ai_coordinate=None) -> MagicMock:
    return MagicMock(css_selector=css_selector, ai_coordinate=ai_coordinate)


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch(SLEEP_TARGET, new=AsyncMock()):
        yield


async def test_no_action_type_does_nothing():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, None, _locator())
    browser.navigate.assert_not_awaited()
    browser.click.assert_not_awaited()


async def test_navigate_uses_input_value():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "navigate", None, input_value="https://example.com")
    browser.navigate.assert_awaited_once_with("https://example.com")


async def test_navigate_falls_back_to_target_element():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "navigate", None, target_element="/home")
    browser.navigate.assert_awaited_once_with("/home")


async def test_navigate_without_url_skips():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "navigate", None)
    browser.navigate.assert_not_awaited()


async def test_click_prefers_css_selector():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "click", _locator(css_selector=".btn"))
    browser.click_element.assert_awaited_once_with(".btn")
    browser.click.assert_not_awaited()


async def test_click_falls_back_to_coordinate_center():
    browser = AsyncMock()
    browser.click_element.side_effect = RuntimeError("css broken")
    locator = _locator(css_selector=".btn", ai_coordinate={"x": 10, "y": 20, "width": 100, "height": 40})
    await _Executor()._execute_step_action(browser, "click", locator)
    browser.click.assert_awaited_once_with(60, 40)


async def test_click_without_css_or_coordinate_does_nothing():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "click", _locator())
    browser.click_element.assert_not_awaited()
    browser.click.assert_not_awaited()


async def test_input_prefers_css_fill():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "input", _locator(css_selector="#name"), input_value="abc")
    browser.fill.assert_awaited_once_with("#name", "abc")


async def test_input_falls_back_to_js_native_setter():
    browser = AsyncMock()
    browser.fill.side_effect = RuntimeError("fill broken")
    locator = _locator(css_selector="#name", ai_coordinate={"x": 0, "y": 0, "width": 10, "height": 10})
    await _Executor()._execute_step_action(browser, "input", locator, input_value="abc")

    browser.click.assert_awaited_once_with(5, 5)
    script, value = browser.execute_javascript.await_args.args
    assert "nativeInputValueSetter" in script
    assert value == "abc"


async def test_hover_uses_css_selector_with_escaped_quotes():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "hover", _locator(css_selector="[data-x='a']"))
    script = browser.execute_javascript.await_args.args[0]
    assert "mouseover" in script
    assert "\\'" in script


async def test_select_uses_css_then_sets_option():
    browser = AsyncMock()
    await _Executor()._execute_step_action(browser, "select", _locator(css_selector="#city"), input_value="北京")
    browser.click_element.assert_awaited_once_with("#city")
    script, value = browser.execute_javascript.await_args.args
    assert "SELECT" in script
    assert value == "北京"


async def test_select_falls_back_to_coordinate_click():
    browser = AsyncMock()
    browser.click_element.side_effect = RuntimeError("css broken")
    locator = _locator(css_selector="#city", ai_coordinate={"x": 2, "y": 4, "width": 20, "height": 10})
    await _Executor()._execute_step_action(browser, "select", locator, input_value="北京")
    browser.click.assert_awaited_once_with(12, 9)


async def test_wait_and_scroll():
    browser = AsyncMock()
    executor = _Executor()
    await executor._execute_step_action(browser, "wait", None)
    browser.execute_javascript.assert_not_awaited()

    await executor._execute_step_action(browser, "scroll", None)
    browser.execute_javascript.assert_awaited_once_with("window.scrollBy(0, 500)")
