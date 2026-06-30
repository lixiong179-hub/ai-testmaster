"""结构化断言扩展类型子 Mixin - UX 体验性断言与安全断言。

将扩展断言（加载状态/响应时间/控制台/网络/敏感数据/XSS）独立成子 Mixin，
与基础断言（URL/文本/可见性）解耦。本 Mixin 不持有独立 __init__，
依赖聚合类提供 self.browser / self._step_start_time_monotonic，
以及跨 Mixin 的 self._get_active_page。
"""
import time
from typing import Any, Dict, List

from app.services.test_execution_engine.models import VerificationError


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


class StructuredExtendedAssertionMixin:
    """结构化断言扩展类型子 Mixin。

    提供 8 个扩展断言方法（loading_visible/loading_hidden/response_time_lt/
    no_console_errors/no_network_errors/text_not_empty/no_sensitive_data/no_xss）
    以及 _get_defect_evidence 缺陷证据辅助方法；依赖聚合类提供
    ``self.browser`` / ``self._step_start_time_monotonic`` 与跨 Mixin 的
    ``_get_active_page``。
    """

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
