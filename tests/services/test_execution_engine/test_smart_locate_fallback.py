"""智能定位三级降级行为护栏（G-8 B4j：`smart_locate_with_ai_fallback` 拆分前置测试）。

覆盖策略1（预定义选择器）→ 策略2（ElementLocatorService）→ 策略3（AI 识别 + CSS 补全）
的逐级降级、重试上限、全失败返回 None。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.test_execution_engine.ai_recognition_mixin import AIRecognitionMixin
from app.services.test_execution_engine.models import StepExecutionError


class _LocateHarness(AIRecognitionMixin):
    """最小宿主：三级定位策略均可单独打桩。"""

    def __init__(
        self,
        browser: Any = None,
        selector: str | None = None,
        locator_service: Any = None,
        element_info: dict[str, Any] | None = None,
        attrs: dict[str, Any] | None = None,
        enable_ai: bool = False,
    ) -> None:
        self.browser = browser
        self.locator_service = locator_service
        self.vision_model = MagicMock() if enable_ai else None
        self.enable_ai_recognition = enable_ai
        self._selector = selector
        self._locate_result = element_info
        self._attrs = attrs
        self.recognize_calls = 0
        self.substitute_calls: list[Any] = []

    def _substitute_parameters_in_action(self, action, test_data):
        self.substitute_calls.append((action, test_data))
        return f"{action}|substituted"

    def _get_element_selector(self, action_text):
        return self._selector

    async def _locate_with_selector(self, selector):
        return self._locate_result

    async def recognize_element_with_ai(self, screenshot, action_description):
        self.recognize_calls += 1
        return self._locate_result

    async def _get_element_attributes_from_coords(self, x, y, width, height):
        return self._attrs


def _make_browser() -> MagicMock:
    browser = MagicMock()
    browser.execute_javascript = AsyncMock(return_value="页面标题")
    browser.take_screenshot = AsyncMock(return_value=b"png")
    return browser


class TestSmartLocateFallback:
    async def test_requires_browser(self):
        engine = _LocateHarness(browser=None)
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine.smart_locate_with_ai_fallback("点击登录")

    async def test_strategy1_predefined_selector_hit(self):
        element_info = {"css_selector": "#login"}
        engine = _LocateHarness(browser=_make_browser(), selector="#login", element_info=element_info)

        result = await engine.smart_locate_with_ai_fallback("点击登录", {"user": "alice"})

        assert result == element_info
        assert engine.substitute_calls == [("点击登录", {"user": "alice"})]
        assert engine.recognize_calls == 0

    async def test_strategy1_failure_falls_to_locator_service(self):
        element_info = {"x": 1, "y": 2}
        locator_service = MagicMock()
        locator_service.smart_locate_element = AsyncMock(return_value=element_info)
        engine = _LocateHarness(browser=_make_browser(), selector="#login", locator_service=locator_service)
        engine._locate_with_selector = AsyncMock(side_effect=Exception("selector broken"))

        result = await engine.smart_locate_with_ai_fallback("点击登录")

        assert result == element_info
        engine.browser.execute_javascript.assert_awaited_once_with("document.title")

    async def test_strategy2_failure_falls_to_ai(self):
        element_info = {"x": 5, "y": 6}
        locator_service = MagicMock()
        locator_service.smart_locate_element = AsyncMock(side_effect=Exception("service down"))
        engine = _LocateHarness(
            browser=_make_browser(),
            locator_service=locator_service,
            element_info=element_info,
            attrs={"id": "auto"},
            enable_ai=True,
        )

        result = await engine.smart_locate_with_ai_fallback("点击提交")

        assert result is element_info
        assert result["css_selector"] == "#auto"
        assert engine.recognize_calls == 1

    async def test_ai_path_enriches_css_selector(self):
        element_info = {"x": 10, "y": 20, "width": 30, "height": 40}
        engine = _LocateHarness(
            browser=_make_browser(), element_info=element_info, attrs={"id": "submit"}, enable_ai=True
        )

        result = await engine.smart_locate_with_ai_fallback("点击提交")

        assert result is element_info
        assert result["css_selector"] == "#submit"

    async def test_ai_path_without_attrs_returns_raw_info(self):
        element_info = {"x": 10, "y": 20}
        engine = _LocateHarness(browser=_make_browser(), element_info=element_info, attrs=None, enable_ai=True)

        result = await engine.smart_locate_with_ai_fallback("点击提交")

        assert result == element_info
        assert "css_selector" not in result

    async def test_ai_path_retries_until_success(self):
        element_info = {"x": 10, "y": 20}
        engine = _LocateHarness(
            browser=_make_browser(), element_info=element_info, attrs={"tag": "button"}, enable_ai=True
        )

        async def _recognize(screenshot, action_description):
            engine.recognize_calls += 1
            return None if engine.recognize_calls == 1 else element_info

        engine.recognize_element_with_ai = _recognize

        result = await engine.smart_locate_with_ai_fallback("点击提交", max_retries=3)

        assert result is element_info
        assert engine.recognize_calls == 2

    async def test_ai_attempts_capped_by_max_retries(self):
        engine = _LocateHarness(browser=_make_browser(), element_info=None, attrs=None, enable_ai=True)

        result = await engine.smart_locate_with_ai_fallback("点击提交", max_retries=2)

        assert result is None
        assert engine.recognize_calls == 2

    async def test_ai_path_tolerates_screenshot_exception(self):
        element_info = {"x": 1, "y": 1}
        engine = _LocateHarness(browser=_make_browser(), element_info=element_info, attrs=None, enable_ai=True)
        engine.browser.take_screenshot = AsyncMock(side_effect=[Exception("shot failed"), b"png"])

        result = await engine.smart_locate_with_ai_fallback("点击提交", max_retries=2)

        assert result is element_info
        assert engine.recognize_calls == 1

    async def test_all_strategies_fail_returns_none(self):
        engine = _LocateHarness(browser=_make_browser())

        assert await engine.smart_locate_with_ai_fallback("点击提交") is None
