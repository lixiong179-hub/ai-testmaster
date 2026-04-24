"""Link Fetcher Content Mixin - 处理不同类型的内容解析

职责:
    - JSON内容解析与认证失败检测
    - HTML内容提取与认证页面检测
    - Markdown内容清理
    - 自动内容类型识别
"""
import re
import json
from typing import Any, Tuple
from bs4 import BeautifulSoup
from loguru import logger
from app.core.constants import AUTH_FAILURE_KEYWORDS


class LinkFetcherContentMixin:
    """内容处理Mixin - 提供JSON/HTML/Markdown/自动识别的处理能力

    设计意图:
        与LinkFetcherCoreMixin组合使用，CoreMixin负责HTTP请求和异常处理，
        ContentMixin负责响应内容的解析和转换。

    依赖:
        - self.session: 由CoreMixin.__init__创建的requests.Session
        - self.timeout: 由CoreMixin.__init__设置的超时时间
    """

    def _process_json(self, content: str) -> Tuple[bool, str, str]:
        """处理JSON内容"""
        try:
            data = json.loads(content)
            if self._detect_auth_failure_in_json(data):
                return False, "", "认证失败：响应内容包含错误标识"
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            return True, formatted, "json"
        except json.JSONDecodeError:
            return True, content[:5000], "text"

    def _detect_auth_failure_in_json(self, data: Any) -> bool:
        """检测JSON响应中是否包含认证失败的典型字段"""
        if isinstance(data, dict):
            error_fields = ("error", "errors", "code", "status", "statusCode")
            for key in error_fields:
                if key in data:
                    val = str(data[key]).lower()
                    if any(kw in val for kw in AUTH_FAILURE_KEYWORDS):
                        return True
                    if key == "code" and data[key] in (401, 403, "401", "403"):
                        return True
            for v in data.values():
                if isinstance(v, (dict, list)) and self._detect_auth_failure_in_json(v):
                    return True
        elif isinstance(data, list):
            for item in data[:10]:
                if self._detect_auth_failure_in_json(item):
                    return True
        return False

    def _process_html(self, content: str) -> Tuple[bool, str, str]:
        """处理HTML内容，提取文本"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            lower = content.lower()
            auth_keywords = (
                'please sign in', 'sign in to continue', 'unauthorized access',
                'access denied', 'auth required', '请登录', '请先登录', '登录后可继续',
            )
            has_auth_hint = any(kw in lower for kw in auth_keywords)
            has_form = '<form' in lower
            if has_auth_hint and has_form:
                return False, "", "认证失败：页面显示需要登录或无权限访问"
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            if len(text) > 5000:
                text = text[:5000] + "\n\n[内容已截断，超长内容请查看原始文档]"
            return True, text, "html"
        except Exception as e:
            logger.warning(f"HTML解析失败: {str(e)}")
            return True, content[:5000], "text"

    def _process_markdown(self, content: str) -> Tuple[bool, str, str]:
        """处理Markdown内容"""
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000] + "\n\n[内容已截断]"
        return True, cleaned, "markdown"

    def _process_auto(self, content: str) -> Tuple[bool, str, str]:
        """自动识别并处理内容"""
        try:
            json.loads(content)
            return self._process_json(content)
        except json.JSONDecodeError:
            pass
        if '<html' in content.lower() or '<!doctype' in content.lower():
            return self._process_html(content)
        lower = content.strip().lower()
        if any(kw in lower for kw in ('unauthorized', 'forbidden', 'invalid token', 'token失效', '认证失败', '登录', 'login')):
            if len(content.strip()) < 500:
                return False, "", "认证失败：响应内容包含错误标识"
        return True, content[:5000], "text"
