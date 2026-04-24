"""Link Fetcher Core Mixin - 带认证的链接内容获取服务核心逻辑
负责初始化和HTTP请求，内容处理委托给ContentMixin
"""
import requests
from typing import Optional, Dict, Any, Tuple
from loguru import logger
from app.utils.http_utils import build_auth_headers


class LinkFetcherCoreMixin:
    """带认证的链接内容获取服务核心逻辑

    职责:
        - 初始化HTTP会话和超时配置
        - 提供fetch_content主入口方法
        - 处理HTTP异常和错误响应

    支持的认证方式:
        1. 无认证 (none)
        2. Basic Auth (basic) - 用户名+密码
        3. Bearer Token (bearer) - Authorization: Bearer <token>
        4. API Key (api_key) - 自定义Header的API Key
        5. Cookie认证 (cookie) - 通过Cookie传递认证信息
    """

    def __init__(self, timeout: int = 30):
        """初始化服务

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_content(
        self,
        url: str,
        auth_type: str = "none",
        auth_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, str]:
        """获取链接内容（主入口）

        根据Content-Type头分发到对应的处理方法（定义在ContentMixin中）。

        Args:
            url: 链接地址
            auth_type: 认证类型
            auth_config: 认证配置

        Returns:
            (成功标志, 内容, 内容类型/错误信息)
        """
        try:
            headers = build_auth_headers(auth_type, auth_config or {})
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
            logger.error(f"连接失败: {url}, {e}")
            return False, "", "连接失败，请检查链接地址"
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
            logger.error(f"获取链接内容异常: {url}, {e}")
            return False, "", "获取内容失败"
