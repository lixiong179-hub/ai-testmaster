"""Link Fetcher Service - 带认证的链接内容获取服务
支持多种认证方式：Basic Auth、Bearer Token、API Key、Cookie、无认证
"""

from app.services.link_fetcher.core_mixin import LinkFetcherCoreMixin
from app.services.link_fetcher.content_mixin import LinkFetcherContentMixin
from app.services.link_fetcher.ui_mixin import LinkFetcherUIMixin


class LinkFetcherService(LinkFetcherCoreMixin, LinkFetcherContentMixin, LinkFetcherUIMixin):
    """带认证的链接内容获取服务

    支持的认证方式：
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
        LinkFetcherCoreMixin.__init__(self, timeout)


# 全局单例实例，保持向后兼容
link_fetcher_service = LinkFetcherService()


__all__ = ["LinkFetcherService", "link_fetcher_service"]
