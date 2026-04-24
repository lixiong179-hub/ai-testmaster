"""Link Fetcher Service - 兼容代理模块

所有实现已迁移到 link_fetcher/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.link_fetcher import LinkFetcherService, link_fetcher_service

__all__ = ["LinkFetcherService", "link_fetcher_service"]
