"""Structured verify/assertion support for execution steps.

支持两类断言语法：
1. 基础断言：text_contains/text_equals/text_matches/visible/not_visible/url_contains/url_equals
2. 扩展断言：loading_visible/loading_hidden/response_time_lt/no_console_errors/
   no_network_errors/text_not_empty/no_sensitive_data/no_xss
"""
import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.test_execution_engine.action_executor_verify_captcha_mixin import (
    ActionExecutorVerifyCaptchaMixin,
)
from app.services.test_execution_engine.models import StepExecutionError, VerificationError
from app.utils.ai_client_parser import parse_ai_json_object


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

# 敏感数据检测 JS 脚本 —— 在浏览器上下文中执行，返回发现的敏感数据列表
_SENSITIVE_DATA_CHECK_JS = """() => {
    const findings = [];
    const bodyText = document.body ? document.body.innerText || '' : '';
    document.querySelectorAll('input[type="password"]').forEach(input => {
        const v = input.value || '';
        if (v && !/^[\\s•\\*]+$/.test(v)) {
            findings.push({type: 'password_plaintext',
                detail: 'input[type=password] contains non-mask value'});
        }
    });
    if (/eyJ[A-Za-z0-9_-]{10,}/.test(bodyText)) {
        findings.push({type: 'jwt_token', detail: 'JWT token pattern (eyJ) found in page text'});
    }
    if (/sk-[A-Za-z0-9]{20,}/.test(bodyText)) {
        findings.push({type: 'api_key', detail: 'API key pattern (sk-) found in page text'});
    }
    if (/1[3-9]\\d{9}/.test(bodyText)) {
        findings.push({type: 'phone_number', detail: 'Chinese phone number pattern found in page text'});
    }
    if (/\\d{17}[\\dXx]/.test(bodyText)) {
        findings.push({type: 'id_card', detail: 'ID card number pattern found in page text'});
    }
    return findings;
}"""

# XSS 检测 JS 脚本 —— 检查 DOM 中是否存在未转义的脚本标签
_XSS_CHECK_JS = """() => {
    const findings = [];
    const bodyHtml = document.body ? document.body.innerHTML || '' : '';
    const patterns = [
        {re: /<script[^>]*>[\\s\\S]*?alert\\s*\\(/gi, name: 'script_alert'},
        {re: /<img[^>]+onerror\\s*=/gi, name: 'img_onerror'},
        {re: /<svg[^>]+onload\\s*=/gi, name: 'svg_onload'},
        {re: /javascript:\\s*alert/gi, name: 'javascript_uri'},
    ];
    patterns.forEach(({re, name}) => {
        re.lastIndex = 0;
        if (re.test(bodyHtml)) {
            findings.push({type: 'xss_payload',
                detail: `XSS pattern '${name}' detected in DOM`});
        }
    });
    return findings;
}"""


class StructuredAssertionMixin(ActionExecutorVerifyCaptchaMixin):
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

    def _get_defect_evidence(self) -> Dict[str, Any]:
        """获取浏览器缺陷证据，browser 或 get_defect_evidence 不可用时返回空结构。"""
        if not self.browser or not hasattr(self.browser, "get_defect_evidence"):
            return {
                "console_errors": [], "network_failures": [],
                "memory_leak_suspect": None, "uncaught_exceptions": [],
            }
        try:
            return self.browser.get_defect_evidence()
        except Exception:
            return {
                "console_errors": [], "network_failures": [],
                "memory_leak_suspect": None, "uncaught_exceptions": [],
            }

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

    # ------------------------------------------------------------------
    # 扩展断言：体验性 + 安全
    # ------------------------------------------------------------------

    async def _assert_loading_visible(self, params: Dict[str, Any]) -> None:
        """检查加载指示器当前可见。"""
        locator = params.get("locator")
        if not locator:
            raise VerificationError("loading_visible 断言缺少选择器")
        page = self._get_active_page()
        try:
            visible = await page.is_visible(locator)
        except Exception as exc:
            raise VerificationError(f"loading_visible 断言执行异常: {exc}") from exc
        if not visible:
            raise VerificationError(f"加载指示器不可见: {locator}")

    async def _assert_loading_hidden(self, params: Dict[str, Any]) -> None:
        """等待加载指示器不可见，超时10秒则失败。"""
        locator = params.get("locator")
        if not locator:
            raise VerificationError("loading_hidden 断言缺少选择器")
        page = self._get_active_page()
        try:
            await page.wait_for_selector(locator, state="hidden", timeout=10000)
        except Exception as exc:
            raise VerificationError(f"加载指示器未在10秒内隐藏: {locator}") from exc

    async def _assert_response_time_lt(self, params: Dict[str, Any]) -> None:
        """断言步骤响应时间低于阈值（毫秒）。"""
        threshold_ms = params.get("threshold_ms", 0)
        if threshold_ms <= 0:
            raise VerificationError(f"response_time_lt 阈值必须为正整数: {threshold_ms}")
        page = self._get_active_page()
        try:
            await page.wait_for_load_state("networkidle")
        except Exception as exc:
            raise VerificationError(f"等待网络空闲超时: {exc}") from exc
        start_mono = getattr(self, "_step_start_time_monotonic", None)
        if start_mono is None:
            raise VerificationError("步骤开始时间未记录，无法计算响应时间")
        elapsed_ms = (time.monotonic() - start_mono) * 1000
        if elapsed_ms > threshold_ms:
            raise VerificationError(
                f"响应时间断言失败: 实际耗时 {elapsed_ms:.0f}ms, 阈值 {threshold_ms}ms"
            )

    async def _assert_no_console_errors(self, params: Dict[str, Any]) -> None:
        """断言无控制台错误，支持 exclude: 模式排除特定错误。"""
        evidence = self._get_defect_evidence()
        console_errors: List[Dict[str, str]] = evidence.get("console_errors", [])
        exclude_patterns: List[str] = params.get("exclude_patterns", [])
        if exclude_patterns:
            console_errors = [
                err for err in console_errors
                if not any(pat in err.get("message", "") for pat in exclude_patterns)
            ]
        if console_errors:
            error_details = "; ".join(
                f"[{e.get('type', 'error')}] {e.get('message', '')}" for e in console_errors
            )
            raise VerificationError(f"控制台存在错误: {error_details}")

    async def _assert_no_network_errors(self, params: Dict[str, Any]) -> None:
        """断言无网络请求失败。"""
        evidence = self._get_defect_evidence()
        network_failures: List[Dict[str, Any]] = evidence.get("network_failures", [])
        if network_failures:
            failure_details = "; ".join(
                f"[{f.get('method', '')} {f.get('url', '')} status={f.get('status', 0)}]"
                for f in network_failures
            )
            raise VerificationError(f"网络请求失败: {failure_details}")

    async def _assert_text_not_empty(self, params: Dict[str, Any]) -> None:
        """断言元素文本非空且非纯空白。"""
        locator = params.get("locator")
        if not locator:
            raise VerificationError("text_not_empty 断言缺少选择器")
        page = self._get_active_page()
        try:
            element = await page.wait_for_selector(locator, timeout=5000)
            if not element:
                raise VerificationError(f"未找到元素: {locator}")
            text_content = await element.text_content()
        except VerificationError:
            raise
        except Exception as exc:
            raise VerificationError(f"获取元素文本异常: {exc}") from exc
        if text_content is None or text_content.strip() == "":
            raise VerificationError(f"元素文本为空: {locator}")

    async def _assert_no_sensitive_data(self, params: Dict[str, Any]) -> None:
        """断言页面无敏感数据暴露（P0缺陷）。"""
        page = self._get_active_page()
        findings: List[Dict[str, str]] = []
        try:
            dom_findings = await page.evaluate(_SENSITIVE_DATA_CHECK_JS)
            if isinstance(dom_findings, list):
                findings.extend(dom_findings)
        except Exception as exc:
            raise VerificationError(f"敏感数据检测执行异常: {exc}") from exc
        evidence = self._get_defect_evidence()
        for failure in evidence.get("network_failures", []):
            url = failure.get("url", "")
            if any(pat in url for pat in ("eyJ", "sk-", "token", "secret", "password")):
                findings.append({
                    "type": "sensitive_in_network",
                    "detail": f"敏感关键词出现在请求URL中: {url[:100]}",
                })
        if findings:
            detail_str = "; ".join(
                f"[P0] {f.get('type', '')}: {f.get('detail', '')}" for f in findings
            )
            raise VerificationError(f"敏感数据暴露: {detail_str}")

    async def _assert_no_xss(self, params: Dict[str, Any]) -> None:
        """断言页面无XSS漏洞（检查DOM中未转义的脚本标签）。"""
        page = self._get_active_page()
        findings: List[Dict[str, str]] = []
        try:
            xss_findings = await page.evaluate(_XSS_CHECK_JS)
            if isinstance(xss_findings, list):
                findings.extend(xss_findings)
        except Exception as exc:
            raise VerificationError(f"XSS检测执行异常: {exc}") from exc
        if findings:
            detail_str = "; ".join(
                f"{f.get('type', '')}: {f.get('detail', '')}" for f in findings
            )
            raise VerificationError(f"XSS漏洞检测: {detail_str}")

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
    "_EXTENDED_ASSERTION_PATTERN",
]
