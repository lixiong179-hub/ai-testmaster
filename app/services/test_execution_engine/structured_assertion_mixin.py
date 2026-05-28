"""Structured verify/assertion support for execution steps."""
import asyncio
import json
import re
from typing import Any, Dict, Optional

from app.services.test_execution_engine.action_executor_verify_captcha_mixin import (
    ActionExecutorVerifyCaptchaMixin,
)
from app.services.test_execution_engine.models import StepExecutionError, VerificationError
from app.utils.ai_client_parser import parse_ai_json_object


_STRUCTURED_ASSERTION_PREFIXES = ("[text_", "[visible", "[not_visible", "[url_")
_ASSERTION_PATTERN = re.compile(
    r"^\[(text_contains|text_equals|text_matches|visible|not_visible|url_contains|url_equals)\](.*)$",
    re.DOTALL,
)


class StructuredAssertionMixin(ActionExecutorVerifyCaptchaMixin):
    async def _execute_verify(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        text = action_info.get("text", "")
        if text.strip().startswith(_STRUCTURED_ASSERTION_PREFIXES):
            await self._execute_structured_assertion(text, action_info)
            return
        await super()._execute_verify(action_info, step_id)

    def _parse_assertion_syntax(self, text: str) -> Optional[tuple[str, Optional[str], str]]:
        text = (text or "").strip()
        match = _ASSERTION_PATTERN.match(text)
        if not match:
            return None
        assertion_type = match.group(1)
        rest = match.group(2)
        locator = None
        expected = rest
        if rest.startswith("["):
            end = rest.find("]")
            if end >= 0:
                bracket_value = rest[1:end]
                tail = rest[end + 1:]
                if assertion_type.startswith("url_") and tail == "":
                    expected = bracket_value
                else:
                    locator = bracket_value
                    expected = tail
        return assertion_type, locator, expected

    async def _execute_structured_assertion(self, text: str, action_info: Dict[str, Any]) -> None:
        parsed = self._parse_assertion_syntax(text)
        if not parsed:
            raise VerificationError("无法解析结构化断言语法")
        assertion_type, locator, expected = parsed
        if assertion_type.startswith("url_"):
            await self._assert_url(assertion_type, expected)
        elif assertion_type in ("text_contains", "text_equals", "text_matches"):
            await self._assert_text(assertion_type, locator, expected, action_info)
        elif assertion_type in ("visible", "not_visible"):
            await self._assert_visibility(assertion_type, locator, expected, action_info)
        else:
            raise VerificationError("无法解析结构化断言语法")

    def _get_active_page(self):
        if self.browser is None:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None)
        if page is None:
            raise StepExecutionError("浏览器页面未初始化")
        return page

    async def _assert_url(self, assertion_type: str, expected: str) -> None:
        page = self._get_active_page()
        actual = getattr(page, "url", "")
        if assertion_type == "url_contains":
            if expected not in actual:
                raise VerificationError(f"URL包含断言失败: 期望包含 '{expected}', 实际URL '{actual}'")
        elif actual != expected:
            raise VerificationError(f"URL相等断言失败: 期望 '{expected}', 实际URL '{actual}'")

    async def _assert_text(
        self,
        assertion_type: str,
        locator: Optional[str],
        expected: str,
        action_info: Dict[str, Any],
    ) -> None:
        if locator:
            page = self._get_active_page()
            element = await page.wait_for_selector(locator, timeout=5000)
            if not element:
                raise VerificationError(f"未找到元素: {locator}")
            actual = await element.text_content()
            actual = actual or ""
        else:
            target = action_info.get("target_element")
            if not target:
                raise VerificationError("缺少 target_element")
            found = await self._locate_with_ai_vision(target)
            actual = found.get("text") or ""

        if assertion_type == "text_contains" and expected not in actual:
            raise VerificationError(f"文本包含断言失败: 期望包含 '{expected}', 实际文本 '{actual}'")
        if assertion_type == "text_equals" and expected != actual:
            raise VerificationError(f"文本相等断言失败: 期望 '{expected}', 实际文本 '{actual}'")
        if assertion_type == "text_matches" and not re.search(expected, actual):
            raise VerificationError(f"文本正则断言失败: 期望匹配 '{expected}', 实际文本 '{actual}'")

    async def _assert_visibility(
        self,
        assertion_type: str,
        locator: Optional[str],
        expected: str,
        action_info: Dict[str, Any],
    ) -> None:
        should_be_visible = assertion_type == "visible"
        if locator:
            page = self._get_active_page()
            try:
                element = await page.wait_for_selector(locator, timeout=5000)
                visible = bool(element and await element.is_visible())
            except Exception:
                visible = False
        else:
            target = action_info.get("target_element") or expected
            if not target:
                raise VerificationError("缺少 target_element")
            if not self.vision_model:
                raise VerificationError("需要AI视觉模型")
            try:
                found = await self._locate_with_ai_vision(target)
                visible = bool(found.get("visible", found.get("found", False)))
            except Exception:
                if should_be_visible:
                    raise VerificationError("可见性断言失败")
                visible = False

        if should_be_visible and not visible:
            raise VerificationError("可见性断言失败")
        if not should_be_visible and visible:
            raise VerificationError("不可见断言失败")

    async def _locate_with_ai_vision(self, target: str) -> Dict[str, Any]:
        if not self.vision_model:
            raise VerificationError("需要AI视觉模型")
        screenshot = await self.browser.take_screenshot()
        prompt = f"请在截图中定位并识别目标元素: {target}。返回JSON，包含found、text、visible、reason字段。"
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                self.vision_model.analyze_image,
                screenshot,
                prompt,
            )
        except Exception as exc:
            raise VerificationError(str(exc)) from exc
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if not json_match:
            raise VerificationError("无法解析AI视觉定位结果")
        result = parse_ai_json_object(json_match.group())
        if result is None:
            raise VerificationError("无法解析AI视觉定位结果")
        if not result.get("found", result.get("visible", False)):
            raise VerificationError("AI视觉未找到元素")
        return result


__all__ = [
    "StructuredAssertionMixin",
    "_STRUCTURED_ASSERTION_PREFIXES",
    "_ASSERTION_PATTERN",
]
