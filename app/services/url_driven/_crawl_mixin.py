"""站点探索 - 链接发现与爬取控制 Mixin。

负责从 PageSnapshot 的导航链接中提取可探索的同源绝对 URL，
执行黑名单过滤与去重，供 SiteExplorer 在 BFS 阶段决定下一批待探索页面。

同源限制基于 scheme+host，避免爬虫越界到第三方站点（如统计、CDN 外链），
黑名单过滤用于规避登出/删除等破坏性路径，防止探索过程误操作用户数据。
"""
from typing import TYPE_CHECKING, List
from urllib.parse import urljoin, urlparse

from app.core.config import settings

if TYPE_CHECKING:
    from app.services.url_driven.site_explorer import PageSnapshot


class CrawlMixin:
    """链接发现与爬取控制 Mixin。

    提供 _discover_links 与同源/黑名单过滤能力，供 SiteExplorer 在 BFS
    阶段调用以决定下一批待探索页面，自身不持有浏览器或网络资源。
    """

    def _discover_links(self, snapshot: "PageSnapshot", base_url: str) -> List[str]:
        """从页面快照的导航链接中提取可探索的绝对 URL。

        过滤规则：
        1. 仅保留与 base_url 同 scheme+host 的同源链接，避免爬取第三方站点；
        2. 命中 URL_QUICK_TEST_BLACKLIST 路径（如 /logout、/delete）的危险链接剔除；
        3. 去重，保证同一 URL 只入队一次。

        Args:
            snapshot: 已采集的页面快照，其 navigation 字段含 {text, href} 链接清单。
            base_url: 探索入口 URL，用于同源判定与相对路径补全。

        Returns:
            可探索的绝对 URL 列表（已去重），可能为空。
        """
        discovered: List[str] = []
        seen = set()
        for nav in snapshot.navigation:
            href = nav.get("href") or ""
            absolute_url = self._normalize_url(href, base_url)
            if not absolute_url:
                continue
            # 仅同源 + 非黑名单 + 未访问过的链接才入队
            if (
                self._is_same_origin(absolute_url, base_url)
                and not self._is_blacklisted(absolute_url)
                and absolute_url not in seen
            ):
                seen.add(absolute_url)
                discovered.append(absolute_url)
        return discovered

    def _normalize_url(self, href: str, base_url: str) -> str:
        """将相对/绝对 href 补全为绝对 URL，剔除锚点与 javascript: 伪协议。

        锚点（#fragment）指向同一页面内位置，无探索价值；
        javascript:/mailto: 等伪协议无法用浏览器导航加载，直接丢弃。
        """
        if not href:
            return ""
        stripped = href.strip()
        # 伪协议与纯锚点不具可探索性，统一过滤
        if stripped.startswith(("javascript:", "mailto:", "tel:", "#")):
            return ""
        absolute = urljoin(base_url, stripped)
        # 移除锚点片段，避免同页不同锚被误判为不同页面
        parsed = urlparse(absolute)
        return parsed._replace(fragment="").geturl()

    def _is_same_origin(self, url: str, base_url: str) -> bool:
        """判定 url 与 base_url 是否同源（scheme + hostname 一致）。

        端口不参与判定，因部分站点将资源分布在多个端口（如 8080 与 3000）；
        深层属性缺失时保守判定为非同源，避免误爬第三方。
        """
        try:
            target = urlparse(url)
            base = urlparse(base_url)
            target_host = target.hostname or ""
            base_host = base.hostname or ""
            return target.scheme in ("http", "https") and target_host == base_host
        except (ValueError, TypeError):
            return False

    def _is_blacklisted(self, url: str) -> bool:
        """判定 URL 路径是否命中危险路径黑名单。

        匹配策略为路径子串包含，覆盖 /user/logout、/api/delete-all 等变体；
        黑名单来源 URL_QUICK_TEST_BLACKLIST 配置项，运行时可调。
        """
        try:
            path = urlparse(url).path.lower()
        except (ValueError, TypeError):
            return False
        blacklist = settings.URL_QUICK_TEST_BLACKLIST or []
        return any(keyword.lower() in path for keyword in blacklist)
