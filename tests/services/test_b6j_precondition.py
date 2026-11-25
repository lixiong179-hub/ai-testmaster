"""B6j 护栏：数学验证码求解与自动登录编排。"""

from types import SimpleNamespace

import pytest

from app.services.precondition.login_mixin import LoginMixin
from app.services.precondition.models import (
    LoginError,
    LoginFormInfo,
    PreconditionError,
    PreconditionTimingConfig,
)
from app.services.precondition.utils import solve_captcha_math


class FakeElement:
    def __init__(self, page: "FakePage"):
        self.page = page

    async def fill(self, text: str) -> None:
        self.page.filled.append(text)

    async def click(self) -> None:
        self.page.clicks += 1


class FakePage:
    def __init__(self):
        self.filled: list[str] = []
        self.clicks = 0
        self.mouse = SimpleNamespace(click=self._noop)
        self.keyboard = SimpleNamespace(press=self._noop, type=self._noop)

    async def _noop(self, *_args, **_kwargs):
        return None

    async def query_selector(self, _selector: str) -> FakeElement:
        return FakeElement(self)


class FakeBrowser:
    """get_page_info / execute_javascript / take_screenshot 的可控替身。"""

    def __init__(self, url="http://app/home", title="首页", form_count=0, screenshot=b"png-bytes"):
        self.page = FakePage()
        self._page = self.page
        self.url = url
        self.title = title
        self.form_count = form_count
        self.screenshot = screenshot
        self.screenshot_calls = 0
        self.fail_screenshot_after: int | None = None

    @staticmethod
    def _resolve(value):
        if isinstance(value, Exception):
            raise value
        return value

    async def take_screenshot(self) -> bytes:
        self.screenshot_calls += 1
        if self.fail_screenshot_after is not None and self.screenshot_calls > self.fail_screenshot_after:
            raise RuntimeError("截图失败")
        return self.screenshot

    async def get_page_info(self) -> dict:
        return {"url": self.url}

    async def execute_javascript(self, script: str):
        if "document.title" in script:
            return self._resolve(self.title)
        return self._resolve(self.form_count)


def make_login_form(with_captcha: bool = False, complete: bool = True) -> LoginFormInfo:
    if not complete:
        return LoginFormInfo(username_input={"x": 0, "y": 0, "width": 10, "height": 10})
    return LoginFormInfo(
        username_input={"x": 0, "y": 0, "width": 10, "height": 10},
        password_input={"x": 0, "y": 20, "width": 10, "height": 10},
        submit_button={"x": 0, "y": 40, "width": 10, "height": 10},
        captcha_input={"x": 0, "y": 60, "width": 10, "height": 10} if with_captcha else None,
        captcha_image={"x": 0, "y": 80, "width": 10, "height": 10} if with_captcha else None,
    )


def make_service(browser, login_form, captcha_result="1234", wait=1):
    service = LoginMixin()
    service.browser_controller = browser
    service.vision_model = object()

    async def _recognize(_screenshot):
        return login_form

    async def _solve(_captcha_image):
        return captcha_result

    service._recognize_login_form = _recognize
    service._recognize_and_solve_captcha = _solve
    service._timing_config = PreconditionTimingConfig(max_login_wait_time=wait, wait_interval=0)
    return service


class TestSolveCaptchaMath:
    @pytest.mark.parametrize(
        "response,expected",
        [
            ("3 + 5 = ?", "8"),
            ("7－2=?", "5"),
            ("6×7", "42"),
            ("5*3", "15"),
            ("9÷2", "4"),
            ("4＋6", "10"),
        ],
    )
    def test_arithmetic(self, response, expected):
        assert solve_captcha_math(response) == expected

    def test_division_by_zero_returns_dividend(self):
        assert solve_captcha_math("8/0") == "8"

    def test_empty_response(self):
        assert solve_captcha_math("") == ""

    def test_single_number(self):
        assert solve_captcha_math("验证码: 4821") == "4821"

    def test_multiple_numbers_prefers_last_short_one(self):
        assert solve_captcha_math("12 345 6789") == "6789"

    def test_alphanumeric_filters_noise(self):
        assert solve_captcha_math("Captcha: abcd") == "abcd"

    def test_all_noise_returns_empty(self):
        assert solve_captcha_math("captcha code") == ""

    def test_cleaned_residual_text_keeps_fullwidth_colon(self):
        # 清理正则只识别半角冒号，全角「：」会保留（既有行为）
        assert solve_captcha_math("答案：★★★") == "：★★★"

    def test_too_long_residual_text_returns_empty(self):
        assert solve_captcha_math("答案：" + "★" * 15) == ""


class TestPerformLogin:
    @pytest.mark.asyncio
    async def test_missing_browser_raises_precondition_error(self):
        service = LoginMixin()
        service.browser_controller = None
        service.vision_model = None

        with pytest.raises(PreconditionError, match="浏览器或视觉模型未初始化"):
            await service._perform_login("user", "pwd")

    @pytest.mark.asyncio
    async def test_incomplete_form_raises_login_error(self):
        service = make_service(FakeBrowser(), make_login_form(complete=False))

        with pytest.raises(LoginError, match="未能识别完整的登录表单"):
            await service._perform_login("user", "pwd")

    @pytest.mark.asyncio
    async def test_happy_path_without_captcha(self):
        browser = FakeBrowser()
        service = make_service(browser, make_login_form())

        await service._perform_login("user", "pwd")

        assert browser.page.filled == ["user", "pwd"]
        assert browser.page.clicks == 1
        assert browser.screenshot_calls == 1

    @pytest.mark.asyncio
    async def test_captcha_is_filled(self):
        browser = FakeBrowser()
        service = make_service(browser, make_login_form(with_captcha=True), captcha_result="8888")

        await service._perform_login("user", "pwd")

        assert browser.page.filled == ["user", "pwd", "8888"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("captcha_result", ["无法识别", ""])
    async def test_captcha_failure_raises(self, captcha_result):
        service = make_service(FakeBrowser(), make_login_form(with_captcha=True), captcha_result=captcha_result)

        with pytest.raises(LoginError, match="验证码识别失败"):
            await service._perform_login("user", "pwd")

    @pytest.mark.asyncio
    async def test_url_still_login_times_out_with_debug_screenshot(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        browser = FakeBrowser(url="http://app/login")
        service = make_service(browser, make_login_form())

        with pytest.raises(LoginError, match="登录超时"):
            await service._perform_login("user", "pwd")

        assert browser.screenshot_calls == 2
        assert list((tmp_path / "logs" / "debug").glob("login_failed_*.png"))

    @pytest.mark.asyncio
    async def test_debug_screenshot_failure_is_swallowed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        browser = FakeBrowser(url="http://app/auth")
        browser.fail_screenshot_after = 1
        service = make_service(browser, make_login_form())

        with pytest.raises(LoginError, match="登录超时"):
            await service._perform_login("user", "pwd")

    @pytest.mark.asyncio
    async def test_title_check_failure_counts_as_logged_out(self):
        browser = FakeBrowser(title=RuntimeError("JS 不支持"), form_count=0)
        service = make_service(browser, make_login_form())

        await service._perform_login("user", "pwd")

        assert browser.page.clicks == 1

    @pytest.mark.asyncio
    async def test_form_probe_failure_counts_as_form_present(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        browser = FakeBrowser(title="请登录", form_count=RuntimeError("JS 不支持"))
        service = make_service(browser, make_login_form())

        with pytest.raises(LoginError, match="登录超时"):
            await service._perform_login("user", "pwd")

    @pytest.mark.asyncio
    async def test_zero_wait_raises_without_polling(self):
        browser = FakeBrowser(url="http://app/login")
        service = make_service(browser, make_login_form(), wait=0)

        with pytest.raises(LoginError, match="轮询结束后未确认登录成功"):
            await service._perform_login("user", "pwd")
        assert browser.screenshot_calls == 1

    @pytest.mark.asyncio
    async def test_empty_title_without_login_form_is_success(self):
        browser = FakeBrowser(title="", form_count=0)
        service = make_service(browser, make_login_form())

        await service._perform_login("user", "pwd")

        assert browser.page.clicks == 1

    @pytest.mark.asyncio
    async def test_intermediate_failed_poll_keeps_waiting(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        browser = FakeBrowser(title="请登录", form_count=1)
        service = make_service(browser, make_login_form(), wait=2)

        with pytest.raises(LoginError, match="登录超时"):
            await service._perform_login("user", "pwd")
        assert browser.screenshot_calls == 2

    @pytest.mark.asyncio
    async def test_login_form_present_keeps_waiting_then_succeeds(self):
        browser = FakeBrowser(url="http://app/home", title="欢迎", form_count=2)
        service = make_service(browser, make_login_form(), wait=2)

        calls = {"n": 0}
        original = browser.execute_javascript

        async def _flaky_probe(script: str):
            if "document.title" not in script:
                calls["n"] += 1
                if calls["n"] == 1:
                    return 2
            return await original(script)

        browser.execute_javascript = _flaky_probe

        await service._perform_login("user", "pwd")

        assert browser.page.clicks == 1
