"""SiteExplorer 边界场景与内部方法单元测试。

覆盖 site_explorer.py 未被 test_site_explorer.py 主流程覆盖的分支：
- _capture_current / _navigate_and_capture 无活动页兜底（203,216）
- _get_cached_sitemap / _set_cached_sitemap 异常降级（241-242,256-257）
- _get_redis_client 懒加载与连接失败降级（265-281）
- 登录成功但登录后快照采集失败仅保留登录页（140,206-208）
- BFS 已访问 URL continue 去重（185）
"""
import sys
import types
from typing import Any

from app.services.url_driven.site_explorer import SiteMap

from tests.services.url_driven.conftest import (
    FakeController,
    FakePage,
    PageData,
    build_page_snapshot,
    cache_key_for,
)

ENTRY = "https://example.com/"


def _use_redis(explorer, fake_redis, monkeypatch) -> None:
    monkeypatch.setattr(explorer, "_get_redis_client", lambda: fake_redis)


class TestCaptureGuards:
    """_capture_current / _navigate_and_capture 无活动页兜底（203,216）。"""

    async def test_capture_current_no_active_page(self, explorer) -> None:
        assert await explorer._capture_current(FakeController()) is None

    async def test_navigate_and_capture_no_active_page(self, explorer) -> None:
        assert await explorer._navigate_and_capture(FakeController(), ENTRY) is None


class TestCacheErrorPaths:
    """缓存读写异常降级（241-242,256-257）+ 空 SiteMap 不写缓存（BUG 3 源头修复）。"""

    async def test_get_cached_sitemap_swallows_json_error(
        self, explorer, fake_redis, monkeypatch
    ) -> None:
        monkeypatch.setattr(explorer, "_get_redis_client", lambda: fake_redis)
        fake_redis.store[cache_key_for(ENTRY)] = "not-json"
        assert explorer._get_cached_sitemap(cache_key_for(ENTRY)) is None

    def test_get_cached_sitemap_no_redis_returns_none(self, explorer, monkeypatch) -> None:
        monkeypatch.setattr(explorer, "_get_redis_client", lambda: None)
        assert explorer._get_cached_sitemap("k") is None

    def test_set_cached_sitemap_swallows_set_error(self, explorer, monkeypatch) -> None:
        class _RaisingRedis:
            def set(self, key: str, value: str, ex: Any = None) -> bool:
                raise RuntimeError("set fail")

        monkeypatch.setattr(explorer, "_get_redis_client", lambda: _RaisingRedis())
        # 用非空 pages 才会进入 set 调用路径；空 pages 直接跳过无法覆盖异常分支
        page = build_page_snapshot("https://example.com", navigation=[])
        site_map = SiteMap(
            entry_url=ENTRY, pages=[page], max_depth_reached=0,
            explored_count=1, skipped_count=0, cache_key="k",
        )
        explorer._set_cached_sitemap("k", site_map)  # 不抛即通过

    def test_set_cached_sitemap_skips_empty_pages(self, explorer, fake_redis, monkeypatch) -> None:
        """空 SiteMap 不写缓存，避免前次失败污染后续 launch（BUG 3 源头修复）。"""
        monkeypatch.setattr(explorer, "_get_redis_client", lambda: fake_redis)
        empty_site_map = SiteMap(
            entry_url=ENTRY, pages=[], max_depth_reached=0,
            explored_count=0, skipped_count=1, cache_key="k",
        )
        explorer._set_cached_sitemap("k", empty_site_map)
        assert fake_redis.set_calls == []
        assert "k" not in fake_redis.store


class TestGetRedisClientLifecycle:
    """_get_redis_client 懒加载与连接失败降级（265-281）。"""

    def test_returns_none_when_disabled(self, explorer) -> None:
        explorer._redis_available = False
        assert explorer._get_redis_client() is None

    def test_returns_cached_client(self, explorer, fake_redis) -> None:
        explorer._redis_client = fake_redis
        assert explorer._get_redis_client() is fake_redis

    def test_degrades_when_from_url_fails(self, explorer, monkeypatch) -> None:
        fake_mod = types.ModuleType("redis_stub")

        def raising_from_url(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("conn fail")

        fake_mod.from_url = raising_from_url
        monkeypatch.setitem(sys.modules, "redis", fake_mod)
        assert explorer._get_redis_client() is None
        assert explorer._redis_available is False

    def test_degrades_when_ping_fails(self, explorer, monkeypatch) -> None:
        class _Client:
            def ping(self) -> bool:
                raise RuntimeError("ping fail")

        fake_mod = types.ModuleType("redis_stub")
        fake_mod.from_url = lambda *a, **kw: _Client()
        monkeypatch.setitem(sys.modules, "redis", fake_mod)
        assert explorer._get_redis_client() is None
        assert explorer._redis_available is False


class TestExplorePostLoginSnapshotFail:
    """登录成功但登录后快照采集失败，仅保留登录页（140,206-208）。"""

    async def test_post_login_snapshot_failure_keeps_login_page(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        entry = "https://app.example.com/login"
        pages_data = {
            entry: PageData(
                url=entry, title="登录",
                nav_raw=[{"text": "d", "href": "/d"}], login_state=True,
            ),
        }
        visible = {
            'input[type="password"]', 'input[name*="user" i]', 'button[type="submit"]',
        }
        page = FakePage(pages_data, visible_selectors=visible, login_succeeds=True)
        patch_browser["page"] = page

        counter = {"n": 0}
        original = explorer._capture_page_snapshot

        async def flaky_snapshot(p: Any) -> Any:
            counter["n"] += 1
            if counter["n"] == 2:
                raise RuntimeError("snapshot fail")
            return await original(p)

        monkeypatch.setattr(explorer, "_capture_page_snapshot", flaky_snapshot)

        site_map = await explorer.explore(
            entry, credentials={"username": "u", "password": "p"}
        )
        assert site_map.explored_count == 1
        assert site_map.pages[0].is_login_page is True


class TestBfsSkipsVisitedUrl:
    """BFS 已访问 URL continue 去重分支（185）。"""

    async def test_bfs_skips_duplicate_url(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        a, b, c = (
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        )
        pages_data = {
            ENTRY: PageData(url=ENTRY, title="首页", nav_raw=[
                {"text": "A", "href": "/a"}, {"text": "B", "href": "/b"}], login_state=False),
            a: PageData(url=a, title="A", nav_raw=[{"text": "C", "href": "/c"}], login_state=False),
            b: PageData(url=b, title="B", nav_raw=[{"text": "C", "href": "/c"}], login_state=False),
            c: PageData(url=c, title="C", nav_raw=[], login_state=False),
        }
        page = FakePage(pages_data)
        patch_browser["page"] = page

        site_map = await explorer.explore(ENTRY)
        urls = [p.url for p in site_map.pages]
        # c 被两页 discover 重复入队，第二次 continue 跳过未重复采集
        assert urls.count(c) == 1
        assert set(urls) == {ENTRY, a, b, c}
