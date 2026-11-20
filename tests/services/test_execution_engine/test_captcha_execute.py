"""验证码执行链路单元测试（`_execute_captcha` 拆分护栏）。

背景：G-8 B4 批次要把 `_execute_captcha`（C901 = 18）拆成阶段方法，
拆分前先补齐行为护栏，确保「识别重试 / 输入框定位 / CSS 与坐标双通道填写」
三条路径在拆分前后完全一致。

覆盖：
    - 前置校验：浏览器 / 视觉模型未初始化
    - 识别成功：首轮即返回结果
    - 识别重试：首轮空结果 → 次轮成功
    - 识别超时：全部重试超时 → 抛 StepExecutionError
    - 输入框定位：placeholder 命中 / 回退最后一个文本输入框 / 找不到抛错
    - 填写：CSS 选择器成功 / 选择器失败降级坐标方式
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.test_execution_engine.action_executor_verify_captcha_mixin import (
    ActionExecutorVerifyCaptchaMixin,
    CAPTCHA_MAX_RETRIES,
)
from app.services.test_execution_engine.ai_recognition_mixin import AIRecognitionMixin
from app.services.test_execution_engine.models import StepExecutionError

_MATH_RESPONSE = '{"captcha_type": "math", "captcha_original": "3+5=?", "captcha_result": "8", "confidence": 0.95}'
_EMPTY_RESPONSE = '{"captcha_result": null, "error": "未找到验证码"}'


class _CaptchaExecutor(ActionExecutorVerifyCaptchaMixin, AIRecognitionMixin):
    """最小可用宿主：只提供 Mixin 依赖的 browser / vision_model。"""

    def __init__(self, browser: Any = None, vision_model: Any = None) -> None:
        self.browser = browser
        self.vision_model = vision_model


def _make_browser(inputs: list[dict[str, Any]]) -> MagicMock:
    browser = MagicMock()
    browser.get_all_input_elements = AsyncMock(return_value=inputs)
    browser.take_screenshot = AsyncMock(return_value=b"fake-png")
    browser.fill = AsyncMock(return_value=True)
    browser.click = AsyncMock(return_value=None)
    browser.execute_javascript = AsyncMock(return_value=True)
    return browser


def _make_vision(side_effect) -> MagicMock:
    vision = MagicMock()
    vision.analyze_image = MagicMock(side_effect=side_effect)
    return vision


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    """把重试等待/坐标点击等待替换为即时返回，避免拖慢用例。"""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(return_value=None))


class TestPreconditions:
    async def test_requires_browser(self):
        executor = _CaptchaExecutor(browser=None, vision_model=_make_vision([_MATH_RESPONSE]))
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await executor._execute_captcha({"text": "输入验证码"}, 1)

    async def test_requires_vision_model(self):
        executor = _CaptchaExecutor(browser=_make_browser([]), vision_model=None)
        with pytest.raises(StepExecutionError, match="视觉模型未初始化"):
            await executor._execute_captcha({"text": "输入验证码"}, 1)


class TestRecognition:
    async def test_success_on_first_attempt(self):
        browser = _make_browser([{"id": "captcha", "placeholder": "请输入验证码", "type": "text"}])
        vision = _make_vision([_MATH_RESPONSE])
        executor = _CaptchaExecutor(browser=browser, vision_model=vision)

        await executor._execute_captcha({"text": "输入验证码"}, 1)

        assert vision.analyze_image.call_count == 1
        browser.fill.assert_awaited_once_with("#captcha", "8")

    async def test_retries_after_empty_result(self):
        browser = _make_browser([{"id": "captcha", "placeholder": "验证码", "type": "text"}])
        vision = _make_vision([_EMPTY_RESPONSE, _MATH_RESPONSE])
        executor = _CaptchaExecutor(browser=browser, vision_model=vision)

        await executor._execute_captcha({"text": "输入验证码"}, 1)

        assert vision.analyze_image.call_count == 2
        browser.fill.assert_awaited_once_with("#captcha", "8")

    async def test_timeout_on_all_attempts_raises(self):
        browser = _make_browser([{"id": "captcha", "placeholder": "验证码", "type": "text"}])
        vision = _make_vision([TimeoutError(), TimeoutError()])
        executor = _CaptchaExecutor(browser=browser, vision_model=vision)

        with pytest.raises(StepExecutionError, match="超时"):
            await executor._execute_captcha({"text": "输入验证码"}, 1)

        assert vision.analyze_image.call_count == CAPTCHA_MAX_RETRIES
        browser.fill.assert_not_awaited()


class TestInputTargeting:
    async def test_falls_back_to_last_text_input(self):
        inputs = [
            {"type": "text", "name": "username"},
            {"type": "password", "name": "pwd"},
            {"type": "text", "name": "last-field"},
        ]
        browser = _make_browser(inputs)
        executor = _CaptchaExecutor(browser=browser, vision_model=_make_vision([_MATH_RESPONSE]))

        await executor._execute_captcha({"text": "输入验证码"}, 1)

        browser.fill.assert_awaited_once_with("[name='last-field']", "8")

    async def test_missing_input_element_raises(self):
        browser = _make_browser([])
        executor = _CaptchaExecutor(browser=browser, vision_model=_make_vision([_MATH_RESPONSE]))

        with pytest.raises(StepExecutionError, match="未找到验证码输入框"):
            await executor._execute_captcha({"text": "输入验证码"}, 1)


class TestFilling:
    async def test_falls_back_to_coordinate_when_selector_fill_fails(self):
        target = {"x": 10, "y": 20, "width": 100, "height": 40, "placeholder": "验证码", "type": "text"}
        browser = _make_browser([target])
        browser.fill = AsyncMock(side_effect=Exception("element detached"))
        executor = _CaptchaExecutor(browser=browser, vision_model=_make_vision([_MATH_RESPONSE]))

        await executor._execute_captcha({"text": "输入验证码"}, 1)

        browser.click.assert_awaited_once_with(60, 40)
        script, value = browser.execute_javascript.await_args.args[0], browser.execute_javascript.await_args.args[1]
        assert "document.activeElement" in script
        assert value == "8"
