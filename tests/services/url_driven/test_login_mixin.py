"""LoginMixin 轻量选择器登录单元测试。

覆盖 spec 场景：
14. 选择器登录成功判定：登录后 _detect_login_page 返回 False 则成功
15. 选择器登录失败：未定位到密码框/用户名框/提交按钮 返回 False
"""
from typing import Any, Optional, Set

from app.services.url_driven.site_explorer import SiteExplorer

from tests.services.url_driven.conftest import FakeController, FakePage, PageData

ENTRY = "https://app.example.com/login"

_PASSWORD = 'input[type="password"]'
_USERNAME = 'input[name*="user" i]'
_SUBMIT = 'button[type="submit"]'


def _make_login_page(
    login_succeeds: bool = True, visible: Optional[Set[str]] = None
) -> FakePage:
    """构造一个登录页 FakePage（未 goto，由测试显式 _sync_goto 切 _current）。"""
    return FakePage(
        pages_data={ENTRY: PageData(url=ENTRY, title="登录", nav_raw=[], login_state=True)},
        visible_selectors=visible if visible is not None else {_PASSWORD, _USERNAME, _SUBMIT},
        login_succeeds=login_succeeds,
    )


class TestLoginWithSelectorsSuccess:
    """场景 14：登录成功判定。"""

    async def test_login_success_when_login_page_disappears(self, explorer: SiteExplorer) -> None:
        page = _make_login_page(login_succeeds=True)
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page

        ok = await explorer._login_with_selectors(
            controller, {"username": "u", "password": "p"}
        )

        assert ok is True
        assert _SUBMIT in page.click_log
        assert any(sel == _USERNAME and val == "u" for sel, val in page.fill_log)
        assert any(sel == _PASSWORD and val == "p" for sel, val in page.fill_log)

    async def test_login_success_returns_true_after_post_login_check(
        self, explorer: SiteExplorer
    ) -> None:
        # login_succeeds=True：click 后 login_state=False，_detect_login_page 返回 False
        page = _make_login_page(login_succeeds=True)
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok = await explorer._login_with_selectors(controller, {"username": "x", "password": "y"})
        assert ok is True


class TestLoginWithSelectorsFailure:
    """场景 15：登录失败路径覆盖。"""

    async def test_no_password_input_returns_false(self, explorer: SiteExplorer) -> None:
        page = _make_login_page(visible={_USERNAME, _SUBMIT})
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok = await explorer._login_with_selectors(controller, {"username": "u", "password": "p"})
        assert ok is False
        assert page.click_log == []  # 未到提交步骤

    async def test_no_username_input_returns_false(self, explorer: SiteExplorer) -> None:
        page = _make_login_page(visible={_PASSWORD, _SUBMIT})
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok = await explorer._login_with_selectors(controller, {"username": "u", "password": "p"})
        assert ok is False

    async def test_no_submit_button_returns_false(self, explorer: SiteExplorer) -> None:
        page = _make_login_page(visible={_PASSWORD, _USERNAME})
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok = await explorer._login_with_selectors(controller, {"username": "u", "password": "p"})
        assert ok is False
        assert page.click_log == []

    async def test_incomplete_credentials_returns_false(self, explorer: SiteExplorer) -> None:
        page = _make_login_page()
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok_missing_user = await explorer._login_with_selectors(
            controller, {"password": "p"}
        )
        ok_missing_pass = await explorer._login_with_selectors(
            controller, {"username": "u"}
        )
        assert ok_missing_user is False
        assert ok_missing_pass is False

    async def test_no_active_page_returns_false(self, explorer: SiteExplorer) -> None:
        controller = FakeController()  # active_page 默认 None
        ok = await explorer._login_with_selectors(
            controller, {"username": "u", "password": "p"}
        )
        assert ok is False

    async def test_post_login_still_login_page_returns_false(self, explorer: SiteExplorer) -> None:
        # login_succeeds=False：click 后 login_state 保持 True，判定登录失败
        page = _make_login_page(login_succeeds=False)
        await page.goto(ENTRY)
        controller = FakeController()
        controller._active_page = page
        ok = await explorer._login_with_selectors(controller, {"username": "u", "password": "p"})
        assert ok is False
        assert _SUBMIT in page.click_log  # 已点击但登录态未变


class TestLocateFirstVisible:
    """_locate_first_visible 异常吞并分支覆盖。"""

    async def test_swallows_locator_exception_returns_none(self, explorer: SiteExplorer) -> None:
        class _RaisingPage:
            def locator(self, selector: str) -> Any:
                raise RuntimeError("loc fail")

        res = await explorer._locate_first_visible(_RaisingPage(), ("sel1", "sel2"))
        assert res is None

    async def test_returns_first_visible(self, explorer: SiteExplorer) -> None:
        page = FakePage(
            pages_data={"https://x.com/": PageData(url="https://x.com/", title="x")},
            visible_selectors={"sel2"},
        )
        await page.goto("https://x.com/")
        res = await explorer._locate_first_visible(page, ("sel1", "sel2", "sel3"))
        assert res is not None


class TestWaitLoginSettle:
    """_wait_login_settle 异常吞并与 URL 变化分支覆盖。"""

    async def test_swallows_wait_exceptions(self, explorer: SiteExplorer) -> None:
        url_before = "https://x.com/login"

        class _RaisingPage:
            url = url_before

            async def wait_for_load_state(self, state: str = "load", timeout: int = 0) -> None:
                raise RuntimeError("load fail")

            async def wait_for_url(self, predicate: Any, timeout: int = 0) -> None:
                raise RuntimeError("url fail")

        # 不抛即通过（两个 except 块均被覆盖）
        await explorer._wait_login_settle(_RaisingPage(), 1000)

    async def test_url_changed_skips_wait_for_url(self, explorer: SiteExplorer) -> None:
        # wait_for_load_state 后 url 变化，则跳过 wait_for_url 分支
        class _ChangedPage:
            def __init__(self) -> None:
                self.url = "https://x.com/login"

            async def wait_for_load_state(self, state: str = "load", timeout: int = 0) -> None:
                self.url = "https://x.com/dashboard"
                return None

            async def wait_for_url(self, predicate: Any, timeout: int = 0) -> None:
                raise AssertionError("url 已变化，不应调用 wait_for_url")

        await explorer._wait_login_settle(_ChangedPage(), 1000)


class TestLoginActionException:
    """_login_with_selectors 提交/填写异常降级覆盖（_login_mixin:98-100）。"""

    async def test_fill_exception_returns_false(self, explorer: SiteExplorer) -> None:
        class _RaisingLocatorPage:
            url = ENTRY

            def locator(self, selector: str) -> Any:
                class _L:
                    @property
                    def first(self) -> "_L":
                        return self

                    async def is_visible(self) -> bool:
                        return True

                    async def fill(self, value: str) -> None:
                        raise RuntimeError("fill fail")

                    async def click(self) -> None:
                        pass

                return _L()

        controller = FakeController()
        controller._active_page = _RaisingLocatorPage()
        ok = await explorer._login_with_selectors(
            controller, {"username": "u", "password": "p"}
        )
        assert ok is False
