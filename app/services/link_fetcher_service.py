"""
Link Fetcher Service - 带认证的链接内容获取服务
支持多种认证方式：Basic Auth、Bearer Token、API Key、Cookie、无认证
"""
import requests
import base64
import re
import json
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from app.utils.db_time import utcnow
from bs4 import BeautifulSoup
from loguru import logger
from app.core.config import settings


class LinkFetcherService:
    """
    带认证的链接内容获取服务

    支持的认证方式：
    1. 无认证 (none)
    2. Basic Auth (basic) - 用户名+密码
    3. Bearer Token (bearer) - Authorization: Bearer <token>
    4. API Key (api_key) - 自定义Header的API Key
    5. Cookie认证 (cookie) - 通过Cookie传递认证信息
    """

    def __init__(self, timeout: int = 30):
        """
        初始化服务

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()

    def _build_auth_headers(self, auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
        """
        根据认证类型构建请求头

        Args:
            auth_type: 认证类型
            auth_config: 认证配置

        Returns:
            请求头字典
        """
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
        """
        获取链接内容（主入口）

        Args:
            url: 链接地址
            auth_type: 认证类型
            auth_config: 认证配置

        Returns:
            (成功标志, 内容, 内容类型/错误信息)
        """
        try:
            headers = self._build_auth_headers(auth_type, auth_config or {})

            logger.info(f"开始获取链接内容: {url}, 认证类型: {auth_type}")
            response = self.session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")

            # 根据内容类型处理
            if "application/json" in content_type:
                return self._process_json(response.text)
            elif "text/html" in content_type or "text/plain" in content_type:
                return self._process_html(response.text)
            elif "text/markdown" in content_type or url.endswith((".md", ".markdown")):
                return self._process_markdown(response.text)
            else:
                # 尝试智能判断内容类型
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
                logger.error(f"认证失败 (401): {url}")
                return False, "", "认证失败，请检查用户名密码或Token"
            elif status_code == 403:
                logger.error(f"权限不足 (403): {url}")
                return False, "", "权限不足，无法访问该链接"
            elif status_code == 404:
                logger.error(f"资源不存在 (404): {url}")
                return False, "", "资源不存在 (404)"
            else:
                logger.error(f"HTTP错误: {status_code}, {url}")
                return False, "", f"HTTP错误: {status_code}"
        except Exception as e:
            logger.error(f"获取链接内容异常: {url}, {str(e)}")
            return False, "", f"获取内容异常: {str(e)}"

    def _process_json(self, content: str) -> Tuple[bool, str, str]:
        """处理JSON内容"""
        try:
            data = json.loads(content)
            # 即使 HTTP 200，也要检查响应体里是否有认证失败的典型字段
            if self._detect_auth_failure_in_json(data):
                return False, "", "认证失败：响应内容包含错误标识"
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            return True, formatted, "json"
        except json.JSONDecodeError:
            return True, content[:5000], "text"

    def _detect_auth_failure_in_json(self, data) -> bool:
        """检测 JSON 响应中是否包含认证失败的典型字段/值（即使 HTTP 状态码是 200）"""
        if isinstance(data, dict):
            # {"error": ...} / {"code": 401/403} / {"status": "error" / "unauthorized"}
            error_fields = ("error", "errors", "code", "status", "statusCode")
            for key in error_fields:
                if key in data:
                    val = str(data[key]).lower()
                    auth_keywords = ("unauthorized", "forbidden", "permission", "认证失败", "无权限", "权限", "登录", "invalid", "incorrect", "expired", "token")
                    if any(kw in val for kw in auth_keywords):
                        return True
                    # code 字段值
                    if key == "code" and data[key] in (401, 403, "401", "403"):
                        return True
            # 递归检查嵌套
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
            # 认证失败页面检测：必须同时满足"明确提示需要登录/授权" + "有表单元素"
            # 不再把含 'login' 标签的 SPA 骨架误判为认证失败
            auth_keywords = (
                'please sign in', 'sign in to continue', 'unauthorized access',
                'access denied', 'auth required', '请登录', '请先登录', '登录后可继续',
            )
            has_auth_hint = any(kw in lower for kw in auth_keywords)
            has_form = '<form' in lower
            if has_auth_hint and has_form:
                return False, "", "认证失败：页面显示需要登录或无权限访问"

            # 移除script和style标签
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # 提取正文内容
            text = soup.get_text(separator='\n', strip=True)

            # 清理多余的空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)

            # 如果内容太长，截取前5000字符
            if len(text) > 5000:
                text = text[:5000] + "\n\n[内容已截断，超长内容请查看原始文档]"

            return True, text, "html"
        except Exception as e:
            logger.warning(f"HTML解析失败: {str(e)}")
            return True, content[:5000], "text"

    def _process_markdown(self, content: str) -> Tuple[bool, str, str]:
        """处理Markdown内容"""
        # 清理Markdown中可能存在的敏感信息
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)  # 移除链接但保留文字
        if len(cleaned) > 5000:
            cleaned = cleaned[:5000] + "\n\n[内容已截断]"
        return True, cleaned, "markdown"

    def _process_auto(self, content: str) -> Tuple[bool, str, str]:
        """自动识别并处理内容"""
        # 尝试JSON
        try:
            json.loads(content)
            return self._process_json(content)
        except json.JSONDecodeError:
            pass

        # 尝试HTML
        if '<html' in content.lower() or '<!doctype' in content.lower():
            return self._process_html(content)

        # 纯文本：先检查是否像认证失败消息
        lower = content.strip().lower()
        if any(kw in lower for kw in ('unauthorized', 'forbidden', 'invalid token', 'token失效', '认证失败', '登录', 'login')):
            if len(content.strip()) < 500:
                return False, "", "认证失败：响应内容包含错误标识"
        # 默认作为纯文本处理
        return True, content[:5000], "text"

    def fetch_and_parse_ui_mockup(self, url: str, auth_type: str = "none", auth_config: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any], str]:
        """
        获取并解析UI原型图链接，提取页面结构描述

        适用于：Axure、Figma、Sketch等原型链接

        Args:
            url: 链接地址
            auth_type: 认证类型
            auth_config: 认证配置

        Returns:
            (成功标志, 解析后的描述字典, 错误信息)
        """
        success, content, content_type = self.fetch_content(url, auth_type, auth_config)

        if not success:
            return False, {}, content

        description = {
            "url": url,
            "fetch_time": utcnow().isoformat(),
            "content_type": content_type,
            "title": "",
            "pages": [],
            "elements": [],
            "summary": ""
        }

        # 尝试从HTML中提取页面结构
        if content_type == "html":
            try:
                soup = BeautifulSoup(content, 'html.parser')

                # 提取标题
                title_tag = soup.find('title')
                if title_tag:
                    description["title"] = title_tag.get_text(strip=True)

                # 提取页面链接/导航
                nav_links = soup.find_all('a')
                page_list = []
                for link in nav_links[:20]:  # 限制数量
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if href and text:
                        page_list.append({"text": text, "href": href})
                description["pages"] = page_list

                # 尝试提取表格内容（常见于文档类页面）
                tables = soup.find_all('table')
                table_data = []
                for table in tables[:5]:
                    rows = []
                    for row in table.find_all('tr')[:10]:
                        cells = [cell.get_text(strip=True) for cell in row.find_all(['th', 'td'])]
                        if cells:
                            rows.append(cells)
                    if rows:
                        table_data.append(rows)
                if table_data:
                    description["tables"] = table_data

                # 生成摘要
                description["summary"] = self._generate_ui_summary(description, content_type)

            except Exception as e:
                logger.warning(f"UI原型解析失败: {str(e)}")
                description["summary"] = content[:500] if content else "无法解析页面内容"

        else:
            description["summary"] = content[:1000] if content else "无内容"

        return True, description, ""

    def _generate_ui_summary(self, description: Dict[str, Any], content_type: str) -> str:
        """生成UI描述摘要"""
        summary_parts = []

        if description.get("title"):
            summary_parts.append(f"页面标题: {description['title']}")

        if description.get("pages"):
            page_count = len(description["pages"])
            summary_parts.append(f"包含 {page_count} 个页面链接/导航项")

        if description.get("tables"):
            table_count = len(description["tables"])
            summary_parts.append(f"包含 {table_count} 个表格")

        if not summary_parts:
            summary_parts.append(f"内容类型: {content_type}")
            if description.get("url"):
                summary_parts.append(f"来源: {description['url']}")

        return " | ".join(summary_parts)

    def validate_link_access(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        验证链接是否可访问

        Args:
            url: 链接地址
            auth_type: 认证类型
            auth_config: 认证配置

        Returns:
            (是否可访问, 状态信息)
        """
        success, content, message = self.fetch_content(url, auth_type, auth_config)

        if success:
            return True, "链接可正常访问"
        else:
            return False, message

    def extract_auth_config_from_form(self, html_content: str, form_index: int = 0) -> Optional[Dict[str, Any]]:
        """
        从HTML表单中提取认证信息（实验性功能）

        Args:
            html_content: HTML内容
            form_index: 表单索引

        Returns:
            提取的认证配置或None
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = soup.find_all('form')
            if form_index >= len(forms):
                return None

            form = forms[form_index]
            action = form.get('action', '')

            # 提取input字段
            inputs = {}
            for inp in form.find_all('input'):
                name = inp.get('name', '')
                inp_type = inp.get('type', 'text')
                value = inp.get('value', '')
                if name and inp_type != 'submit' and inp_type != 'button':
                    inputs[name] = value

            return {
                "form_action": action,
                "form_method": form.get('method', 'get').upper(),
                "fields": inputs
            }
        except Exception as e:
            logger.warning(f"表单提取失败: {str(e)}")
            return None


# 全局服务实例
link_fetcher_service = LinkFetcherService()
