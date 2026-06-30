"""Structured verify/assertion support for execution steps.

聚合基础断言子 Mixin 与扩展断言子 Mixin，对外暴露 StructuredAssertionMixin
类与 3 个模块级常量（_STRUCTURED_ASSERTION_PREFIXES / _ASSERTION_PATTERN /
_EXTENDED_ASSERTION_PATTERN），保持原有导入路径兼容。

支持两类断言语法：
1. 基础断言：text_contains/text_equals/text_matches/visible/not_visible/url_contains/url_equals
2. 扩展断言：loading_visible/loading_hidden/response_time_lt/no_console_errors/
   no_network_errors/text_not_empty/no_sensitive_data/no_xss
"""
import re
from typing import Any, Dict, Optional, Tuple

from app.services.test_execution_engine.action_executor_verify_captcha_mixin import (
    ActionExecutorVerifyCaptchaMixin,
)
from app.services.test_execution_engine.models import StepExecutionError, VerificationError
from app.services.test_execution_engine._basic_assertion_mixin import (
    StructuredBasicAssertionMixin,
)
from app.services.test_execution_engine._extended_assertion_mixin import (
    StructuredExtendedAssertionMixin,
)


_STRUCTURED_ASSERTION_PREFIXES = (
    "[text_", "[visible", "[not_visible", "[url_",
    "[loading_visible", "[loading_hidden", "[response_time_lt",
    "[no_console_errors", "[no_network_errors", "[text_not_empty",
    "[no_sensitive_data", "[no_xss",
)

_ASSERTION_PATTERN = re.compile(
    r"^\[(text_contains|text_equals|text_matches|visible|not_visible|url_contains|url_equals)\](.*)$",
    re.DOTALL,
)

_EXTENDED_ASSERTION_PATTERN = re.compile(
    r"^\[(loading_visible|loading_hidden|response_time_lt|no_console_errors"
    r"|no_network_errors|text_not_empty|no_sensitive_data|no_xss)\](.*)$",
    re.DOTALL,
)


class StructuredAssertionMixin(
    StructuredBasicAssertionMixin,
    StructuredExtendedAssertionMixin,
    ActionExecutorVerifyCaptchaMixin,
):
    """结构化断言聚合 Mixin。

    通过继承基础断言子 Mixin（URL/文本/可见性）与扩展断言子 Mixin
    （UX/安全），聚合完整的结构化断言能力；本类保留语法解析、断言分发、
    活动页面获取等编排逻辑。
    """

    async def _execute_verify(self, action_info: Dict[str, Any], step_id: Optional[int]) -> None:
        text = action_info.get("text", "")
        if text.strip().startswith(_STRUCTURED_ASSERTION_PREFIXES):
            await self._execute_structured_assertion(text, action_info)
            return
        await super()._execute_verify(action_info, step_id)

    def _parse_assertion_syntax(self, text: str) -> Optional[Tuple[str, Optional[str], str]]:
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

    def _parse_extended_assertion_syntax(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """解析扩展断言语法，返回 (assertion_type, params) 或 None。"""
        text = (text or "").strip()
        match = _EXTENDED_ASSERTION_PATTERN.match(text)
        if not match:
            return None
        assertion_type = match.group(1)
        rest = match.group(2)
        params: Dict[str, Any] = {}

        if assertion_type in ("loading_visible", "loading_hidden", "text_not_empty"):
            if rest.startswith("["):
                end = rest.find("]")
                if end >= 0:
                    params["locator"] = rest[1:end]
                    params["description"] = rest[end + 1:]
        elif assertion_type == "response_time_lt":
            threshold_str = rest.strip()
            if not threshold_str.isdigit() or int(threshold_str) <= 0:
                raise VerificationError(
                    f"response_time_lt 阈值必须为正整数，实际: '{threshold_str}'"
                )
            params["threshold_ms"] = int(threshold_str)
        elif assertion_type == "no_console_errors":
            if rest.startswith("exclude:"):
                exclude_str = rest[8:]
                params["exclude_patterns"] = [
                    p.strip() for p in exclude_str.split(",") if p.strip()
                ]
        return assertion_type, params

    async def _execute_structured_assertion(self, text: str, action_info: Dict[str, Any]) -> None:
        extended = self._parse_extended_assertion_syntax(text)
        if extended:
            assertion_type, params = extended
            await self._dispatch_extended_assertion(assertion_type, params)
            return
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

    async def _dispatch_extended_assertion(
        self, assertion_type: str, params: Dict[str, Any],
    ) -> None:
        """分发扩展断言到对应的处理方法。"""
        dispatch_map = {
            "loading_visible": self._assert_loading_visible,
            "loading_hidden": self._assert_loading_hidden,
            "response_time_lt": self._assert_response_time_lt,
            "no_console_errors": self._assert_no_console_errors,
            "no_network_errors": self._assert_no_network_errors,
            "text_not_empty": self._assert_text_not_empty,
            "no_sensitive_data": self._assert_no_sensitive_data,
            "no_xss": self._assert_no_xss,
        }
        handler = dispatch_map.get(assertion_type)
        if not handler:
            raise VerificationError(f"未知的扩展断言类型: {assertion_type}")
        await handler(params)

    def _get_active_page(self):
        if self.browser is None:
            raise StepExecutionError("浏览器未初始化")
        page = getattr(self.browser, "active_page", None)
        if page is None:
            raise StepExecutionError("浏览器页面未初始化")
        return page


__all__ = [
    "StructuredAssertionMixin",
    "_STRUCTURED_ASSERTION_PREFIXES",
    "_ASSERTION_PATTERN",
    "_EXTENDED_ASSERTION_PATTERN",
]
