"""链接内容Mixin - 从URL抓取页面内容并提取文本。
"""
import requests
import base64
import re
import json
from typing import Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from loguru import logger


class LinkFetcherContentMixin:
    def _build_auth_headers(self, auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        if auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            if username and password:
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"
        elif auth_type == "bearer":
            token = auth_config.get("token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            api_key = auth_config.get("api_key", "")
            header_name = auth_config.get("api_key_header", "X-API-Key")
            if api_key:
                headers[header_name] = api_key
        elif auth_type == "cookie":
            cookie = auth_config.get("cookie", "")
            if cookie:
                headers["Cookie"] = cookie
        return headers

    def fetch_content(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, str]:
        try:
            headers = self._build_auth_headers(auth_type, auth_config or {})
            logger.info(f"开始获取链接内容: {url}, 认证类型: {auth_type}")
            response = self.session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return self._process_json(response.text)
            elif "text/html" in content_type or "text/plain" in content_type:
                return self._process_html(response.text)
            elif "text/markdown" in content_type or url.endswith((".md", ".markdown")):
                return self._process_markdown(response.text)
            else:
                return self._process_auto(response.text)
        except requests.exceptions.Timeout:
            logger.error(f"获取链接内容超时: {url}")
            return False, "", "请求超时"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接失败: {url}, {str(e)}")
            return False, "", f"连接失败: {str(e)}"
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 401:
                return False, "", "认证失败，请检查用户名密码或Token"
            elif status_code == 403:
                return False, "", "权限不足，无法访问该链接"
            elif status_code == 404:
                return False, "", "资源不存在 (404)"
            else:
                return False, "", f"HTTP错误: {status_code}"
        except Exception as e:
            logger.error(f"获取链接内容异常: {url}, {str(e)}")
            return False, "", f"获取内容异常: {str(e)}"

    def _process_json(self, content: str) -> Tuple[bool, str, str]:
        try:
            data = json.loads(content)
            if self._detect_auth_failure_in_json(data):
                return False, "", "认证失败：响应内容包含错误标识"
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            return True, formatted, "json"
        except json.JSONDecodeError:
            return True, content[:5000], "text"

    def _detect_auth_failure_in_json(self, data) -> bool:
        if isinstance(data, dict):
            error_fields = ("error", "errors", "code", "status", "statusCode")
            for key in error_fields:
                if key in data:
                    val = str(data[key]).lower()
                    auth_keywords = ("unauthorized", "forbidden", "permission", "认证失败", "无权限", "权限", "登录", "invalid", "incorrect", "expired", "token")
                    if any(kw in val for kw in auth_keywords):
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
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000] + "\n\n[内容已截断]"
        return True, cleaned, "markdown"

    def _process_auto(self, content: str) -> Tuple[bool, str, str]:
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
