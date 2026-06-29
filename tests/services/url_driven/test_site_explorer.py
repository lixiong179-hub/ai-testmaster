"""SiteExplorer.explore 主流程单元测试（spec 场景 1-8、10、18）。"""
import json

from app.core.config import settings
from app.services.url_driven.site_explorer import PageSnapshot, SiteMap

from tests.services.url_driven.conftest import (
    FakePage,
    PageData,
    cache_key_for,
    make_a11y_node,
)

ENTRY = "https://example.com/"


def _use_redis(explorer, fake_redis, monkeypatch) -> None:
    """让 explorer 使用 FakeRedis 客户端。"""
    monkeypatch.setattr(explorer, "_get_redis_client", lambda: fake_redis)


class TestExplorePublicSite:
    """场景 1：公开站点 BFS 多页探索。"""

    async def test_bfs_multiple_pages_returns_sitemap(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        page_a, page_b = "https://example.com/a", "https://example.com/b"
        pages_data = {
            ENTRY: PageData(
                url=ENTRY, title="首页",
                a11y=make_a11y_node("root", children=[make_a11y_node("button", "提交")]),
                nav_raw=[
                    {"text": "A", "href": "/a"},
                    {"text": "B", "href": "https://example.com/b"},
                ],
                login_state=False,
            ),
            page_a: PageData(url=page_a, title="A页", nav_raw=[], login_state=False),
            page_b: PageData(url=page_b, title="B页", nav_raw=[], login_state=False),
        }
        patch_browser["page"] = FakePage(pages_data)

        site_map = await explorer.explore(ENTRY)

        assert isinstance(site_map, SiteMap)
        assert site_map.entry_url == ENTRY
        assert site_map.explored_count == 3
        assert site_map.skipped_count == 0
        assert site_map.max_depth_reached >= 1
        assert all(isinstance(p, PageSnapshot) for p in site_map.pages)
        assert site_map.pages[0].url == ENTRY
        assert site_map.pages[0].is_login_page is False
        assert site_map.pages[0].title == "首页"
        assert any(e["role"] == "button" for e in site_map.pages[0].elements)


class TestExploreLoginSiteSuccess:
    """场景 2：登录页 + 凭据 + 登录成功。"""

    async def test_login_success_uses_post_login_snapshot_for_bfs(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        entry = "https://app.example.com/login"
        dashboard = "https://app.example.com/dashboard"
        pages_data = {
            entry: PageData(
                url=entry, title="登录",
                nav_raw=[{"text": "主页", "href": "/dashboard"}],
                login_state=True,
            ),
            dashboard: PageData(url=dashboard, title="主页", nav_raw=[], login_state=False),
        }
        visible = {
            'input[type="password"]',
            'input[name*="user" i]',
            'button[type="submit"]',
        }
        page = FakePage(pages_data, visible_selectors=visible)
        patch_browser["page"] = page

        site_map = await explorer.explore(entry, credentials={"username": "u", "password": "p"})

        # entry 快照被替换为登录后快照（login_state 已切 False），BFS 到 dashboard
        assert site_map.explored_count == 2
        assert site_map.pages[0].is_login_page is False
        assert site_map.pages[0].url == entry
        assert site_map.pages[1].url == dashboard
        # 提交按钮被点击、用户名/密码被填写
        assert 'button[type="submit"]' in page.click_log
        assert any(sel == 'input[type="password"]' and val == "p" for sel, val in page.fill_log)
        assert any(sel == 'input[name*="user" i]' and val == "u" for sel, val in page.fill_log)


class TestExploreLoginSiteFailure:
    """场景 3：登录页 + 凭据错误，登录失败。"""

    async def test_login_failure_keeps_only_login_page(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        entry = "https://app.example.com/login"
        pages_data = {
            entry: PageData(
                url=entry, title="登录",
                nav_raw=[{"text": "主页", "href": "/dashboard"}],
                login_state=True,
            ),
            "https://app.example.com/dashboard": PageData(
                url="https://app.example.com/dashboard", title="主页",
                nav_raw=[], login_state=False,
            ),
        }
        visible = {
            'input[type="password"]', 'input[name*="user" i]', 'button[type="submit"]',
        }
        # login_succeeds=False：提交后 _detect_login_page 仍 True，登录失败
        page = FakePage(pages_data, visible_selectors=visible, login_succeeds=False)
        patch_browser["page"] = page

        site_map = await explorer.explore(entry, credentials={"username": "u", "password": "bad"})

        assert site_map.explored_count == 1
        assert site_map.pages[0].is_login_page is True
        # 未 BFS：goto_log 仅 entry（登录后 _capture_current 不 goto）
        assert page.goto_log == [entry]


class TestExploreLoginSiteNoCredentials:
    """场景 4：登录页但无凭据，仅保留登录页。"""

    async def test_login_page_without_credentials_skips_bfs(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        entry = "https://app.example.com/login"
        pages_data = {
            entry: PageData(
                url=entry, title="登录",
                nav_raw=[{"text": "X", "href": "/x"}],
                login_state=True,
            ),
        }
        page = FakePage(pages_data)
        patch_browser["page"] = page

        site_map = await explorer.explore(entry, credentials=None)

        assert site_map.explored_count == 1
        assert site_map.pages[0].is_login_page is True
        assert page.goto_log == [entry]


class TestExploreCacheHit:
    """场景 5：缓存命中直接返回，不启动浏览器。"""

    async def test_cache_hit_returns_cached_without_browser(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        cached = SiteMap(
            entry_url=ENTRY, pages=[], max_depth_reached=0,
            explored_count=0, skipped_count=0, cache_key=cache_key_for(ENTRY),
        )
        fake_redis.store[cache_key_for(ENTRY)] = json.dumps(cached.to_dict(), ensure_ascii=False)
        patch_browser["page"] = FakePage({})  # 即便配置也不应被使用

        site_map = await explorer.explore(ENTRY)

        assert site_map.entry_url == ENTRY
        assert site_map.explored_count == 0
        # 缓存命中：BrowserControllerV2 未被实例化
        assert patch_browser["instances"] == []
        # 缓存读取消耗一次 get
        assert cache_key_for(ENTRY) in fake_redis.get_calls


class TestExploreCacheWrite:
    """场景 6：探索完成后写入 Redis。"""

    async def test_explore_writes_cache(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        pages_data = {ENTRY: PageData(url=ENTRY, title="首页", nav_raw=[], login_state=False)}
        patch_browser["page"] = FakePage(pages_data)

        await explorer.explore(ENTRY)

        assert len(fake_redis.set_calls) == 1
        key, value, ex = fake_redis.set_calls[0]
        assert key == cache_key_for(ENTRY)
        assert ex == settings.URL_QUICK_TEST_CACHE_TTL
        restored = SiteMap.from_dict(json.loads(value))
        assert restored.entry_url == ENTRY
        assert restored.explored_count == 1


class TestExploreRedisUnavailable:
    """场景 7：Redis 不可用降级，探索正常进行。"""

    async def test_redis_unavailable_degrades_gracefully(
        self, explorer, patch_browser, monkeypatch
    ) -> None:
        monkeypatch.setattr(explorer, "_get_redis_client", lambda: None)
        pages_data = {ENTRY: PageData(url=ENTRY, title="首页", nav_raw=[], login_state=False)}
        patch_browser["page"] = FakePage(pages_data)

        site_map = await explorer.explore(ENTRY)

        assert site_map.explored_count == 1
        assert site_map.pages[0].url == ENTRY


class TestExplorePageTimeout:
    """场景 8：单页 goto 超时不阻断整体探索。"""

    async def test_single_page_timeout_increments_skipped(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        page_a = "https://example.com/a"
        pages_data = {
            ENTRY: PageData(
                url=ENTRY, title="首页",
                nav_raw=[{"text": "A", "href": "/a"}],
                login_state=False,
            ),
            page_a: PageData(url=page_a, title="A", nav_raw=[], login_state=False),
        }
        page = FakePage(pages_data, goto_errors={page_a})
        patch_browser["page"] = page

        site_map = await explorer.explore(ENTRY)

        assert site_map.explored_count == 1  # 仅 entry
        assert site_map.skipped_count == 1  # page_a 跳过
        assert page.goto_log == [ENTRY, page_a]


class TestExploreMaxDepth:
    """场景 10：BFS 深度受 URL_QUICK_TEST_MAX_DEPTH 限制。"""

    async def test_bfs_respects_max_depth(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        monkeypatch.setattr(settings, "URL_QUICK_TEST_MAX_DEPTH", 2)
        l1, l2, l3 = (
            "https://example.com/l1",
            "https://example.com/l2",
            "https://example.com/l3",
        )
        pages_data = {
            ENTRY: PageData(url=ENTRY, title="首页", nav_raw=[{"text": "L1", "href": "/l1"}], login_state=False),
            l1: PageData(url=l1, title="L1", nav_raw=[{"text": "L2", "href": "/l2"}], login_state=False),
            l2: PageData(url=l2, title="L2", nav_raw=[{"text": "L3", "href": "/l3"}], login_state=False),
            l3: PageData(url=l3, title="L3", nav_raw=[], login_state=False),
        }
        patch_browser["page"] = FakePage(pages_data)

        site_map = await explorer.explore(ENTRY)

        urls = [p.url for p in site_map.pages]
        assert ENTRY in urls and l1 in urls and l2 in urls
        assert l3 not in urls  # depth 3 > max_depth 2，不入队
        assert site_map.max_depth_reached == 2


class TestExploreEntryUnreachable:
    """场景 18：首页不可达返回空 SiteMap。"""

    async def test_entry_unreachable_returns_empty_sitemap(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        _use_redis(explorer, fake_redis, monkeypatch)
        page = FakePage({}, goto_errors={ENTRY})
        patch_browser["page"] = page

        site_map = await explorer.explore(ENTRY)

        assert site_map.explored_count == 0
        assert site_map.skipped_count == 1
        assert site_map.pages == []
        assert site_map.entry_url == ENTRY

    async def test_entry_unreachable_does_not_pollute_cache(
        self, explorer, patch_browser, fake_redis, monkeypatch
    ) -> None:
        """首页不可达产生的空 SiteMap 不写缓存（BUG 3 源头修复端到端验证）。

        场景：前次失败产生的空 SiteMap 不应被写入缓存，否则后续 launch 会命中
        空缓存直接返回，导致 0 用例生成。验证：explore 完成后 Redis 不含该 URL
        的缓存键。
        """
        _use_redis(explorer, fake_redis, monkeypatch)
        page = FakePage({}, goto_errors={ENTRY})
        patch_browser["page"] = page

        await explorer.explore(ENTRY)

        assert fake_redis.set_calls == []
        assert cache_key_for(ENTRY) not in fake_redis.store
