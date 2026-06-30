"""结构化断言基础类型子 Mixin - URL/文本/可见性断言与 AI 视觉定位。

将基础断言逻辑独立成子 Mixin，与扩展断言（UX/安全）解耦。
本 Mixin 不持有独立 __init__，依赖聚合类提供 self.browser /
self.vision_model，以及跨 Mixin 的 self._get_active_page。
"""
import asyncio
import re
from typing import Any, Dict, Optional

from app.services.test_execution_engine.models import VerificationError
from app.utils.ai_client_parser import parse_ai_json_object


class StructuredBasicAssertionMixin:
    """结构化断言基础类型子 Mixin。

    提供 _assert_url / _assert_text / _assert_visibility 三个基础断言方法，
    以及 _locate_with_ai_vision AI 视觉定位辅助方法；依赖聚合类提供
    ``self.browser`` / ``self.vision_model`` 与跨 Mixin 的 ``_get_active_page``。
    """

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
