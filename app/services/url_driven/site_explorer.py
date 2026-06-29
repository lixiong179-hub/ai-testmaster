"""网址驱动快速测试 - 站点探索引擎。

接收一个网址，自动完成登录检测、DOM 快照采集、同源页面流 BFS 发现，
产出结构化 SiteMap，作为后续 URL 自动建项与用例生成的确定性输入。

设计要点：
- 复用 BrowserControllerV2 启动 headless 浏览器，try/finally 确保关闭；
- 用轻量 CSS 选择器（LoginMixin._login_with_selectors）完成自动登录，不依赖 AI，
  登录失败或登录页无凭据时仅保留登录页快照不 BFS；
- 单页超时/加载失败/登录失败均降级跳过，记录 skipped_count，不阻断整体探索；
- SiteMap 经 Redis 缓存，TTL 由 URL_QUICK_TEST_CACHE_TTL 控制，命中直接返回。
"""
import json
from collections import deque
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.config import settings
from app.services.url_driven._crawl_mixin import CrawlMixin
from app.services.url_driven._login_mixin import LoginMixin
from app.services.url_driven._snapshot_mixin import SnapshotMixin
from app.utils.browser_controller_base import BrowserConfig
from app.utils.browser_controller_v2 import BrowserControllerV2


@dataclass
class PageSnapshot:
    """单页 DOM 快照，作为用例生成的确定性输入。

    elements 来源于真实 Accessibility Tree，禁编造；locator 为 Playwright
    定位字符串，css_selector 留空（a11y tree 不含 DOM 选择器）。
    """
    url: str
    title: str
    elements: List[Dict[str, Any]]
    forms: List[Dict[str, Any]]
    navigation: List[Dict[str, str]]
    is_login_page: bool
    screenshot_path: Optional[str]
    captured_at: str


@dataclass
class SiteMap:
    """站点探索产物，含入口 URL、页面快照列表与探索统计。"""
    entry_url: str
    pages: List[PageSnapshot]
    max_depth_reached: int
    explored_count: int
    skipped_count: int
    cache_key: str

    def to_dict(self) -> Dict[str, Any]:
        """序列化为可 JSON 化的字典，供 Redis 缓存存储。"""
        return {
            "entry_url": self.entry_url,
            "pages": [asdict(page) for page in self.pages],
            "max_depth_reached": self.max_depth_reached,
            "explored_count": self.explored_count,
            "skipped_count": self.skipped_count,
            "cache_key": self.cache_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteMap":
        """从字典反序列化 SiteMap，pages 字段重建为 PageSnapshot。"""
        pages = [PageSnapshot(**page) for page in data.get("pages", [])]
        return cls(
            entry_url=data["entry_url"],
            pages=pages,
            max_depth_reached=data["max_depth_reached"],
            explored_count=data["explored_count"],
            skipped_count=data["skipped_count"],
            cache_key=data["cache_key"],
        )


class SiteExplorer(CrawlMixin, SnapshotMixin, LoginMixin):
    """站点探索引擎，输入 URL 产出 SiteMap。

    通过多继承组合 CrawlMixin（链接发现）、SnapshotMixin（快照采集）与
    LoginMixin（选择器登录），自身负责浏览器生命周期、BFS 编排与 Redis 缓存。
    """

    def __init__(self) -> None:
        # 单页超时（毫秒），对齐 BrowserConfig 导航/动作超时，超时跳过该页
        self._page_timeout_ms: int = settings.URL_QUICK_TEST_PAGE_TIMEOUT * 1000
        self._redis_client: Any = None
        self._redis_available: bool = True

    async def explore(self, url: str, credentials: Optional[Dict[str, str]] = None) -> SiteMap:
        """探索站点：缓存校验 → 启动浏览器 → 登录检测 → BFS 采集 → 缓存写入。

        Args:
            url: 探索入口网址。
            credentials: 可选登录凭据 {"username", "password"}，仅当首页判定为登录页时使用。

        Returns:
            SiteMap 探索产物；即便首页采集失败也返回空 pages 的 SiteMap 供上层降级。
        """
        cache_key = f"sitemap:{sha256(url.encode('utf-8')).hexdigest()}"
        cached = self._get_cached_sitemap(cache_key)
        if cached is not None:
            logger.info(f"SiteMap 缓存命中，直接返回: {cache_key}")
            return cached

        controller = BrowserControllerV2(self._build_browser_config())
        pages: List[PageSnapshot] = []
        skipped_count = 0
        max_depth_reached = 0
        try:
            await controller.initialize()
            entry_snapshot = await self._navigate_and_capture(controller, url)
            if entry_snapshot is None:
                # 首页即不可达，整体探索视为失败但返回空 SiteMap 供上层降级处理
                skipped_count += 1
                logger.warning(f"入口页面采集失败，探索终止: {url}")
            else:
                pages.append(entry_snapshot)
                bfs_seed = entry_snapshot
                # 公开站点默认 BFS；登录页场景按登录结果决定是否 BFS
                should_bfs = not entry_snapshot.is_login_page
                if entry_snapshot.is_login_page:
                    if not credentials:
                        # 登录页但未提供凭据：仅保留登录页快照，不 BFS（spec Scenario）
                        logger.info("首页为登录页但未提供凭据，仅探索登录页")
                    else:
                        login_ok = await self._login_with_selectors(controller, credentials)
                        if not login_ok:
                            # 登录失败：仅保留登录页快照，不 BFS（spec Scenario：登录失败降级）
                            logger.info("自动登录失败，仅探索登录页")
                        else:
                            # 登录成功：用登录后页面快照替换登录页快照并作为 BFS 种子
                            relanded = await self._capture_current(controller)
                            if relanded is None:
                                # 登录后页快照采集失败，无有效 BFS 种子，仅保留登录页快照
                                logger.warning("登录后页面快照采集失败，跳过 BFS 仅保留登录页快照")
                            else:
                                pages[-1] = relanded
                                bfs_seed = relanded
                                should_bfs = True
                if should_bfs:
                    bfs_pages, bfs_skipped, bfs_depth = await self._bfs_crawl(
                        controller, bfs_seed, url
                    )
                    pages.extend(bfs_pages)
                    skipped_count += bfs_skipped
                    max_depth_reached = bfs_depth
        finally:
            await controller.close()

        site_map = SiteMap(
            entry_url=url,
            pages=pages,
            max_depth_reached=max_depth_reached,
            explored_count=len(pages),
            skipped_count=skipped_count,
            cache_key=cache_key,
        )
        self._set_cached_sitemap(cache_key, site_map)
        return site_map

    async def _bfs_crawl(
        self, controller: BrowserControllerV2, entry_snapshot: PageSnapshot, base_url: str
    ) -> Tuple[List[PageSnapshot], int, int]:
        """BFS 遍历同源链接逐页采集，深度受 URL_QUICK_TEST_MAX_DEPTH 限制。

        Returns:
            (新增页面快照列表, 跳过页数, 最大到达深度)
        """
        max_depth = settings.URL_QUICK_TEST_MAX_DEPTH
        visited = {entry_snapshot.url}
        queue: deque = deque(
            (link_url, 1) for link_url in self._discover_links(entry_snapshot, base_url)
        )
        pages: List[PageSnapshot] = []
        skipped = 0
        max_depth_reached = 0
        while queue:
            url, depth = queue.popleft()
            if depth > max_depth or url in visited:
                continue
            visited.add(url)
            snapshot = await self._navigate_and_capture(controller, url)
            if snapshot is None:
                skipped += 1
                continue
            pages.append(snapshot)
            max_depth_reached = max(max_depth_reached, depth)
            if depth < max_depth:
                for next_url in self._discover_links(snapshot, base_url):
                    if next_url not in visited:
                        queue.append((next_url, depth + 1))
        return pages, skipped, max_depth_reached

    async def _capture_current(self, controller: BrowserControllerV2) -> Optional[PageSnapshot]:
        """采集当前页快照（不导航），用于登录后重新采集登录后页面。"""
        page = controller.active_page
        if page is None:
            return None
        try:
            return await self._capture_page_snapshot(page)
        except Exception as e:
            logger.warning(f"采集当前页快照失败: {e}")
            return None

    async def _navigate_and_capture(
        self, controller: BrowserControllerV2, url: str
    ) -> Optional[PageSnapshot]:
        """导航到指定 URL 并采集快照，导航超时或失败返回 None。"""
        page = controller.active_page
        if page is None:
            return None
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self._page_timeout_ms)
        except Exception as e:
            logger.warning(f"导航到 {url} 超时或失败，跳过该页: {e}")
            return None
        return await self._capture_current(controller)

    def _build_browser_config(self) -> BrowserConfig:
        """构建 headless 浏览器配置，超时对齐单页超时配置避免卡死。"""
        return BrowserConfig(
            headless=True,
            navigation_timeout=self._page_timeout_ms,
            action_timeout=self._page_timeout_ms,
        )

    def _get_cached_sitemap(self, cache_key: str) -> Optional[SiteMap]:
        """读取 Redis 缓存的 SiteMap，不可用或未命中返回 None。"""
        client = self._get_redis_client()
        if client is None:
            return None
        try:
            raw = client.get(cache_key)
            if raw:
                return SiteMap.from_dict(json.loads(raw))
        except Exception as e:
            logger.warning(f"读取 SiteMap 缓存失败: {e}")
        return None

    def _set_cached_sitemap(self, cache_key: str, site_map: SiteMap) -> None:
        """写入 SiteMap 到 Redis 缓存，TTL 为 URL_QUICK_TEST_CACHE_TTL。

        空 SiteMap（pages 为空）跳过缓存写入：前次失败产生的空探索结果若
        写入缓存，会导致后续 launch 命中空缓存直接返回，0 用例生成（spec BUG 3
        源头修复）。仅缓存有页面快照的探索结果。
        """
        if not site_map.pages:
            logger.info(f"SiteMap 无页面快照，跳过缓存写入避免污染: {cache_key}")
            return
        client = self._get_redis_client()
        if client is None:
            return
        try:
            client.set(
                cache_key,
                json.dumps(site_map.to_dict(), ensure_ascii=False),
                ex=settings.URL_QUICK_TEST_CACHE_TTL,
            )
        except Exception as e:
            logger.warning(f"写入 SiteMap 缓存失败: {e}")

    def _get_redis_client(self) -> Any:
        """懒加载同步 Redis 客户端，连接失败降级返回 None 跳过缓存。

        沿用 rate_limit.py 的同步 redis.from_url 模式保持项目一致；
        缓存读写为 KB 级小数据，同步调用阻塞可忽略。
        """
        if not self._redis_available:
            return None
        if self._redis_client is None:
            try:
                import redis
                self._redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )
                self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis 不可用，站点探索缓存降级为跳过: {e}")
                self._redis_available = False
                self._redis_client = None
        return self._redis_client
