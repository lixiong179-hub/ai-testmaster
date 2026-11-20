"""选择 / 输入动作与自愈选择器构建的行为护栏（G-8 B4g 拆分前置测试）。

覆盖三条高风险路径：
    - `_execute_select`：智能定位 CSS 成功、CSS 失败降级坐标、坐标非法回退预定义选择器、
      预定义选择器成功、全部失败抛错
    - `_execute_input`：测试数据替换（字段命中 / 默认 test 回退首个值）、CSS 填充成功、
      CSS 失败降级坐标 + 原生 setter 注入、智能定位无结果抛错
    - `_build_healed_selector`：id > name > placeholder > class > tag 的优先级与清洗
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.test_execution_engine.action_executor_hover_select_mixin import (
    ActionExecutorHoverSelectMixin,
)
from app.services.test_execution_engine.action_executor_input_click_mixin import (
    ActionExecutorInputClickMixin,
)
from app.services.test_execution_engine.models import StepExecutionError
from app.services.test_execution_engine.self_healing_utils_mixin import (
    SelfHealingUtilsMixin,
)


class _SelectInputHarness(ActionExecutorInputClickMixin, ActionExecutorHoverSelectMixin):
    """最小宿主：只提供 Mixin 依赖的 browser / 定位能力。"""

    def __init__(
        self,
        browser: Any = None,
        element_info: dict[str, Any] | None = None,
        preset_selector: str | None = None,
        enable_ai: bool = True,
    ) -> None:
        self.browser = browser
        self.enable_ai_recognition = enable_ai
        self.locator_service = None
        self._element_info = element_info
        self._preset_selector = preset_selector
        self._locate_calls: list[Any] = []

    async def smart_locate_with_ai_fallback(self, text: str, step_test_data=None):
        self._locate_calls.append((text, step_test_data))
        return self._element_info

    def _get_element_selector(self, action_text: str) -> str | None:
        return self._preset_selector


def _make_browser() -> MagicMock:
    browser = MagicMock()
    browser.fill = AsyncMock(return_value=None)
    browser.click = AsyncMock(return_value=None)
    browser.click_element = AsyncMock(return_value=None)
    browser.hover = AsyncMock(return_value=None)
    browser.execute_javascript = AsyncMock(return_value=None)
    return browser


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    import asyncio

    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))


class TestExecuteSelect:
    async def test_requires_browser(self):
        engine = _SelectInputHarness(browser=None)
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_select({"text": "选择城市"}, 1)

    async def test_css_selector_path_executes_select_js(self):
        browser = _make_browser()
        engine = _SelectInputHarness(
            browser=browser,
            element_info={"css_selector": "select.city", "x": 10, "y": 10},
        )

        await engine._execute_select({"text": "选择城市", "input_value": "上海"}, 1)

        browser.click_element.assert_awaited_once_with("select.city")
        args = browser.execute_javascript.await_args.args
        assert "SELECT" in args[0]
        assert args[1] == "select.city"
        assert args[2] == "上海"
        browser.click.assert_not_awaited()

    async def test_css_failure_falls_back_to_coordinate(self):
        browser = _make_browser()
        browser.click_element = AsyncMock(side_effect=Exception("detached"))
        engine = _SelectInputHarness(
            browser=browser,
            element_info={"css_selector": "select.city", "x": 10, "y": 20, "width": 100, "height": 40},
        )

        await engine._execute_select({"text": "选择城市", "input_value": "上海"}, 1)

        browser.click.assert_awaited_once_with(60, 40)
        args = browser.execute_javascript.await_args.args
        assert "elementFromPoint" in args[0]
        assert args[1:] == (60, 40, "上海")

    async def test_negative_coordinate_falls_back_to_preset_selector(self):
        browser = _make_browser()
        engine = _SelectInputHarness(
            browser=browser,
            element_info={"x": -1, "y": -1, "width": 0, "height": 0},
            preset_selector=".preset-select",
        )

        await engine._execute_select({"text": "选择城市", "input_value": "上海"}, 1)

        browser.click.assert_not_awaited()
        browser.click_element.assert_awaited_once_with(".preset-select")

    async def test_raises_when_nothing_located(self):
        browser = _make_browser()
        engine = _SelectInputHarness(browser=browser, element_info=None, preset_selector=None)

        with pytest.raises(StepExecutionError, match="无法定位选择元素"):
            await engine._execute_select({"text": "选择城市"}, 1)

    async def test_ai_disabled_skips_smart_locate(self):
        browser = _make_browser()
        engine = _SelectInputHarness(browser=browser, preset_selector=".preset-select", enable_ai=False)

        await engine._execute_select({"text": "选择城市"}, 1)

        assert engine._locate_calls == []
        browser.click_element.assert_awaited_once_with(".preset-select")


class TestExecuteInput:
    async def test_requires_browser(self):
        engine = _SelectInputHarness(browser=None)
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_input({"text": "输入用户名"}, 1)

    async def test_css_fill_with_test_data_substitution(self):
        browser = _make_browser()
        engine = _SelectInputHarness(browser=browser, element_info={"css_selector": "#username"})

        await engine._execute_input(
            {"text": "输入 username 字段"},
            1,
            step_test_data={"username": "alice"},
        )

        browser.fill.assert_awaited_once_with("#username", "alice")

    async def test_default_test_value_replaced_by_first_test_data(self):
        browser = _make_browser()
        engine = _SelectInputHarness(browser=browser, element_info={"css_selector": "#remark"})

        await engine._execute_input({"text": "输入内容"}, 1, step_test_data={"remark": "临时备注"})

        browser.fill.assert_awaited_once_with("#remark", "临时备注")

    async def test_css_failure_falls_back_to_native_setter(self):
        browser = _make_browser()
        browser.fill = AsyncMock(side_effect=Exception("element detached"))
        engine = _SelectInputHarness(
            browser=browser,
            element_info={"css_selector": "#username", "x": 0, "y": 0, "width": 20, "height": 10},
        )

        await engine._execute_input({"text": "输入 zhangsan"}, 1)

        browser.click.assert_awaited_once_with(10, 5)
        script, value = browser.execute_javascript.await_args.args
        assert "document.activeElement" in script
        assert value == "zhangsan"

    async def test_raises_when_smart_locate_returns_nothing(self):
        browser = _make_browser()
        engine = _SelectInputHarness(browser=browser, element_info=None)

        with pytest.raises(StepExecutionError, match="无法定位输入元素"):
            await engine._execute_input({"text": "输入用户名"}, 1)


class TestBuildHealedSelector:
    """拆分 `_build_healed_selector` 的优先级护栏（既有 26 例之外的边界）。"""

    @pytest.fixture
    def mixin(self) -> SelfHealingUtilsMixin:
        return SelfHealingUtilsMixin()

    def test_id_wins_over_other_attributes(self, mixin):
        attrs = {"id": "login-btn", "name": "user", "placeholder": "请输入", "tag": "input"}
        assert mixin._build_healed_selector(attrs) == "#login-btn"

    def test_invalid_id_falls_through_to_name(self, mixin):
        attrs = {"id": "!!!", "name": "user_name"}
        assert mixin._build_healed_selector(attrs) == "[name='user_name']"

    def test_placeholder_truncated_to_ten_chars(self, mixin):
        attrs = {"placeholder": "enter username here"}
        assert mixin._build_healed_selector(attrs) == "[placeholder*='enteruser']"

    def test_non_ascii_placeholder_falls_through_to_none(self, mixin):
        """中文 placeholder 被 CSS 标识符清洗清空 -> 不生成选择器（与原实现一致）。"""
        assert mixin._build_healed_selector({"placeholder": "请输入手机号码"}) is None

    def test_class_without_tag_returns_class_selector(self, mixin):
        attrs = {"class": "btn btn-primary extra"}
        assert mixin._build_healed_selector(attrs) == ".btn.btn-primary"

    def test_tag_only(self, mixin):
        assert mixin._build_healed_selector({"tag": "textarea"}) == "textarea"

    def test_empty_attributes_return_none(self, mixin):
        assert mixin._build_healed_selector({}) is None
