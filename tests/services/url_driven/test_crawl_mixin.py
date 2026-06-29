"""CrawlMixin 链接发现与爬取控制单元测试。

覆盖 spec 场景：
9.  黑名单过滤：_is_blacklisted 命中 /logout /delete，_discover_links 过滤掉
11. 同源过滤：_is_same_origin 第三方域名返回 False
- 12. URL 规范化：_normalize_url 处理相对路径、锚点、javascript:/mailto: 伪协议
"""
from typing import Any

from app.core.config import settings
from app.services.url_driven._crawl_mixin import CrawlMixin

from tests.services.url_driven.conftest import build_page_snapshot


class _CrawlTester(CrawlMixin):
    """CrawlMixin 独立测试宿主，不引入浏览器与 Redis 依赖。"""


class TestIsBlacklisted:
    """场景 9：_is_blacklisted 黑名单命中。"""

    def setup_method(self) -> None:
        self.c = _CrawlTester()

    def test_logout_path_hits(self) -> None:
        assert self.c._is_blacklisted("https://x.com/user/logout") is True

    def test_delete_path_hits(self) -> None:
        assert self.c._is_blacklisted("https://x.com/api/delete-all") is True

    def test_reset_path_hits(self) -> None:
        assert self.c._is_blacklisted("https://x.com/account/reset") is True

    def test_normal_path_not_hit(self) -> None:
        assert self.c._is_blacklisted("https://x.com/home/dashboard") is False

    def test_case_insensitive(self) -> None:
        assert self.c._is_blacklisted("https://x.com/LOGOUT") is True

    def test_invalid_url_returns_false(self) -> None:
        # urlparse 容错：非 URL 字符串不抛异常，路径子串匹配
        assert self.c._is_blacklisted("not a url") is False

    def test_empty_blacklist_config(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "URL_QUICK_TEST_BLACKLIST", [])
        assert self.c._is_blacklisted("https://x.com/logout") is False


class TestIsSameOrigin:
    """场景 11：_is_same_origin 同源判定。"""

    def setup_method(self) -> None:
        self.c = _CrawlTester()

    def test_same_host_same_scheme(self) -> None:
        assert self.c._is_same_origin("https://x.com/a", "https://x.com/b") is True

    def test_same_host_diff_port(self) -> None:
        # 端口不参与同源判定
        assert self.c._is_same_origin("https://x.com:8080/a", "https://x.com:3000/b") is True

    def test_third_party_host_returns_false(self) -> None:
        assert self.c._is_same_origin("https://other.com/a", "https://x.com/b") is False

    def test_diff_scheme_returns_false(self) -> None:
        # 仅 http/https 视为有效 scheme
        assert self.c._is_same_origin("ftp://x.com/a", "https://x.com/b") is False

    def test_invalid_url_returns_false(self) -> None:
        assert self.c._is_same_origin("", "https://x.com/b") is False

    def test_none_safe(self) -> None:
        assert self.c._is_same_origin(None, "https://x.com/b") is False  # type: ignore[arg-type]


class TestNormalizeUrl:
    """场景 12：_normalize_url 相对路径/锚点/伪协议处理。"""

    def setup_method(self) -> None:
        self.c = _CrawlTester()

    def test_relative_path_resolved(self) -> None:
        assert self.c._normalize_url("/a", "https://x.com/") == "https://x.com/a"

    def test_relative_with_base_path(self) -> None:
        assert self.c._normalize_url("b", "https://x.com/sec/") == "https://x.com/sec/b"

    def test_absolute_unchanged(self) -> None:
        assert self.c._normalize_url("https://x.com/a", "https://x.com/") == "https://x.com/a"

    def test_anchor_fragment_removed(self) -> None:
        assert self.c._normalize_url("https://x.com/a#sec", "https://x.com/") == "https://x.com/a"

    def test_javascript_pseudo_dropped(self) -> None:
        assert self.c._normalize_url("javascript:void(0)", "https://x.com/") == ""

    def test_mailto_dropped(self) -> None:
        assert self.c._normalize_url("mailto:a@b.com", "https://x.com/") == ""

    def test_tel_dropped(self) -> None:
        assert self.c._normalize_url("tel:123456", "https://x.com/") == ""

    def test_pure_anchor_dropped(self) -> None:
        assert self.c._normalize_url("#section", "https://x.com/a") == ""

    def test_empty_href_returns_empty(self) -> None:
        assert self.c._normalize_url("", "https://x.com/") == ""


class TestDiscoverLinksFilter:
    """场景 9/11/12 组合：_discover_links 同源+黑名单+去重过滤。"""

    def setup_method(self) -> None:
        self.c = _CrawlTester()

    def test_filters_blacklist_and_third_party(self) -> None:
        snap = build_page_snapshot(
            url="https://x.com/",
            navigation=[
                {"text": "home", "href": "/home"},
                {"text": "logout", "href": "/logout"},
                {"text": "delete", "href": "https://x.com/delete"},
                {"text": "ext", "href": "https://other.com/x"},
                {"text": "js", "href": "javascript:void(0)"},
            ],
        )
        links = self.c._discover_links(snap, "https://x.com/")
        assert links == ["https://x.com/home"]

    def test_dedup_same_url(self) -> None:
        snap = build_page_snapshot(
            url="https://x.com/",
            navigation=[
                {"text": "a", "href": "/a"},
                {"text": "a2", "href": "/a"},
                {"text": "a3", "href": "https://x.com/a#frag"},
            ],
        )
        links = self.c._discover_links(snap, "https://x.com/")
        assert links == ["https://x.com/a"]

    def test_empty_navigation_returns_empty(self) -> None:
        snap = build_page_snapshot(url="https://x.com/", navigation=[])
        assert self.c._discover_links(snap, "https://x.com/") == []


class TestParseErrorHandling:
    """_is_same_origin / _is_blacklisted 解析异常兜底覆盖（_crawl_mixin:86-87,97-98）。"""

    def setup_method(self) -> None:
        self.c = _CrawlTester()

    def test_is_same_origin_swallows_parse_error(self, monkeypatch) -> None:
        from app.services.url_driven import _crawl_mixin as crawl_mod

        def raising_parse(url: str) -> Any:
            raise ValueError("parse fail")

        monkeypatch.setattr(crawl_mod, "urlparse", raising_parse)
        assert self.c._is_same_origin("https://x.com", "https://x.com") is False

    def test_is_blacklisted_swallows_parse_error(self, monkeypatch) -> None:
        from app.services.url_driven import _crawl_mixin as crawl_mod

        def raising_parse(url: str) -> Any:
            raise ValueError("parse fail")

        monkeypatch.setattr(crawl_mod, "urlparse", raising_parse)
        assert self.c._is_blacklisted("https://x.com/logout") is False
