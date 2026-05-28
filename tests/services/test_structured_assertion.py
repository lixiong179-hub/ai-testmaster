"""结构化断言单元测试

覆盖范围:
- 语法解析（各种格式）
- 文本断言（有/无定位器，contains/equals/matches，成功/失败）
- 可见性断言（有/无定位器，visible/not_visible，成功/失败）
- URL 断言（contains/equals，成功/失败）
- 回退 AI 视觉验证
- 断言失败时记录期望值与实际值

要求: 不使用Mock，覆盖率>=95%
"""
import pytest
from types import SimpleNamespace

from app.services.test_execution_engine.models import (
    StepExecutionError, VerificationError,
)
from app.services.test_execution_engine.action_executor_verify_captcha_mixin import (
    ActionExecutorVerifyCaptchaMixin,
    _STRUCTURED_ASSERTION_PREFIXES,
    _ASSERTION_PATTERN,
)


class _StubElement:
    def __init__(self, text_content: str | None = "", is_visible: bool = True):
        self._text_content = text_content
        self._is_visible = is_visible

    async def text_content(self) -> str | None:
        return self._text_content

    async def is_visible(self) -> bool:
        return self._is_visible


class _StubPage:
    def __init__(self, url: str = "http://localhost:3000/home/project"):
        self.url = url
        self._elements: dict = {}
        self._wait_for_selector_result: object = None
        self._wait_for_selector_exception: Exception | None = None

    def set_element(self, selector: str, text: str = "", visible: bool = True):
        self._elements[selector] = _StubElement(text, visible)

    def set_wait_for_selector_result(self, result: object, exception: Exception | None = None):
        self._wait_for_selector_result = result
        self._wait_for_selector_exception = exception

    async def wait_for_selector(self, selector: str, timeout: int = 5000):
        if self._wait_for_selector_exception:
            raise self._wait_for_selector_exception
        if self._wait_for_selector_result is not None:
            return self._wait_for_selector_result
        return self._elements.get(selector)


class _StubVisionModel:
    def __init__(self, response: str = '{"found": true, "text": "项目列表", "visible": true}'):
        self._response = response

    def analyze_image(self, screenshot: bytes, prompt: str) -> str:
        return self._response


class _StubBrowser:
    def __init__(self, page: _StubPage | None = None):
        self._page = page
        self._context = None

    @property
    def active_page(self):
        return self._page

    async def take_screenshot(self) -> bytes:
        return b"fake_screenshot"


class _StubEngine(ActionExecutorVerifyCaptchaMixin):
    def __init__(self, browser=None, vision_model=None):
        self.browser = browser
        self.vision_model = vision_model


def _make_browser_with_page(
    url: str = "http://localhost:3000/home/project",
) -> _StubBrowser:
    page = _StubPage(url=url)
    return _StubBrowser(page=page)


# ============================================================
# 语法解析测试
# ============================================================


class TestParseAssertionSyntax:
    def setup_method(self):
        self.engine = _StubEngine()

    def test_text_contains_with_locator(self):
        result = self.engine._parse_assertion_syntax(
            "[text_contains][data-testid=page-title]项目列表"
        )
        assert result == ("text_contains", "data-testid=page-title", "项目列表")

    def test_text_equals_with_locator_in_brackets(self):
        result = self.engine._parse_assertion_syntax(
            "[text_equals][h1]AI TestMaster"
        )
        assert result == ("text_equals", "h1", "AI TestMaster")

    def test_text_equals_without_locator(self):
        result = self.engine._parse_assertion_syntax(
            "[text_equals]AI TestMaster"
        )
        assert result == ("text_equals", None, "AI TestMaster")

    def test_text_contains_without_locator(self):
        result = self.engine._parse_assertion_syntax("[text_contains]项目列表")
        assert result == ("text_contains", None, "项目列表")

    def test_text_matches_with_locator(self):
        result = self.engine._parse_assertion_syntax(
            "[text_matches][data-testid=count]\\d+条记录"
        )
        assert result == ("text_matches", "data-testid=count", "\\d+条记录")

    def test_visible_with_locator(self):
        result = self.engine._parse_assertion_syntax(
            "[visible][data-testid=submit-btn]提交按钮"
        )
        assert result == ("visible", "data-testid=submit-btn", "提交按钮")

    def test_not_visible_with_locator(self):
        result = self.engine._parse_assertion_syntax(
            "[not_visible][data-testid=loading]加载中"
        )
        assert result == ("not_visible", "data-testid=loading", "加载中")

    def test_visible_without_locator(self):
        result = self.engine._parse_assertion_syntax("[visible]提交按钮")
        assert result == ("visible", None, "提交按钮")

    def test_url_contains(self):
        result = self.engine._parse_assertion_syntax("[url_contains]/home/project")
        assert result == ("url_contains", None, "/home/project")

    def test_url_equals(self):
        result = self.engine._parse_assertion_syntax(
            "[url_equals]http://localhost:3000/login"
        )
        assert result == ("url_equals", None, "http://localhost:3000/login")

    def test_url_contains_with_bracket_content(self):
        result = self.engine._parse_assertion_syntax(
            "[url_contains][/home/project]"
        )
        assert result == ("url_contains", None, "/home/project")

    def test_url_equals_with_bracket_content(self):
        result = self.engine._parse_assertion_syntax(
            "[url_equals][http://localhost:3000/login]"
        )
        assert result == ("url_equals", None, "http://localhost:3000/login")

    def test_invalid_syntax_returns_none(self):
        result = self.engine._parse_assertion_syntax("普通验证文本")
        assert result is None

    def test_whitespace_trimmed(self):
        result = self.engine._parse_assertion_syntax("  [text_equals][h1]AI TestMaster  ")
        assert result == ("text_equals", "h1", "AI TestMaster")

    def test_empty_expected_with_locator(self):
        result = self.engine._parse_assertion_syntax("[text_equals][h1]")
        assert result == ("text_equals", "h1", "")

    def test_locator_with_complex_css_selector(self):
        result = self.engine._parse_assertion_syntax(
            "[text_contains][data-testid=my-btn]按钮文字"
        )
        assert result == ("text_contains", "data-testid=my-btn", "按钮文字")

    def test_text_equals_h1_without_brackets(self):
        result = self.engine._parse_assertion_syntax("[text_equals]h1AI TestMaster")
        assert result == ("text_equals", None, "h1AI TestMaster")


class TestAssertionPatternRegex:
    def test_all_assertion_types_recognized(self):
        types = [
            "text_contains", "text_equals", "text_matches",
            "visible", "not_visible", "url_contains", "url_equals",
        ]
        for t in types:
            match = _ASSERTION_PATTERN.match(f"[{t}]value")
            assert match is not None, f"应匹配断言类型: {t}"
            assert match.group(1) == t

    def test_structured_prefixes(self):
        prefixes = _STRUCTURED_ASSERTION_PREFIXES
        assert "[text_" in prefixes
        assert "[visible" in prefixes
        assert "[not_visible" in prefixes
        assert "[url_" in prefixes


# ============================================================
# 文本断言测试
# ============================================================


class TestTextContainsAssertion:
    @pytest.mark.asyncio
    async def test_with_locator_success(self):
        page = _StubPage()
        page.set_element("data-testid=page-title", "项目列表页面")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][data-testid=page-title]项目列表"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure(self):
        page = _StubPage()
        page.set_element("data-testid=page-title", "用户管理")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][data-testid=page-title]项目列表"}
        with pytest.raises(VerificationError, match="文本包含断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure_shows_expected_and_actual(self):
        page = _StubPage()
        page.set_element("data-testid=page-title", "用户管理")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][data-testid=page-title]项目列表"}
        with pytest.raises(VerificationError, match="期望包含 '项目列表'.*实际文本 '用户管理'"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_with_ai_vision(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "text": "项目列表", "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[text_contains]项目列表",
            "target_element": "页面标题",
        }
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_missing_target_element(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains]项目列表"}
        with pytest.raises(VerificationError, match="缺少 target_element"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_no_vision_model(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser, vision_model=None)
        action_info = {
            "text": "[text_contains]项目列表",
            "target_element": "页面标题",
        }
        with pytest.raises(VerificationError, match="需要AI视觉模型"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_element_not_found(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][data-testid=missing]项目列表"}
        with pytest.raises(VerificationError, match="未找到元素"):
            await engine._execute_verify(action_info, step_id=1)


class TestTextEqualsAssertion:
    @pytest.mark.asyncio
    async def test_with_locator_success(self):
        page = _StubPage()
        page.set_element("h1", "AI TestMaster")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]AI TestMaster"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure(self):
        page = _StubPage()
        page.set_element("h1", "AI TestMaster Pro")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]AI TestMaster"}
        with pytest.raises(VerificationError, match="文本相等断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure_shows_expected_and_actual(self):
        page = _StubPage()
        page.set_element("h1", "AI TestMaster Pro")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]AI TestMaster"}
        with pytest.raises(VerificationError, match="期望 'AI TestMaster'.*实际文本 'AI TestMaster Pro'"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_empty_text_content(self):
        page = _StubPage()
        page.set_element("h1", "")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_none_text_content_treated_as_empty(self):
        page = _StubPage()
        element = _StubElement(text_content=None)
        page._elements["h1"] = element
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]"}
        await engine._execute_verify(action_info, step_id=1)


class TestTextMatchesAssertion:
    @pytest.mark.asyncio
    async def test_with_locator_success(self):
        page = _StubPage()
        page.set_element("data-testid=count", "15条记录")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_matches][data-testid=count]\\d+条记录"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure(self):
        page = _StubPage()
        page.set_element("data-testid=count", "无记录")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_matches][data-testid=count]\\d+条记录"}
        with pytest.raises(VerificationError, match="文本正则断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_failure_shows_expected_and_actual(self):
        page = _StubPage()
        page.set_element("data-testid=count", "无记录")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_matches][data-testid=count]\\d+条记录"}
        with pytest.raises(VerificationError, match="期望匹配"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# 可见性断言测试
# ============================================================


class TestVisibleAssertion:
    @pytest.mark.asyncio
    async def test_with_locator_visible_success(self):
        page = _StubPage()
        page.set_element("data-testid=submit-btn", "提交按钮", visible=True)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[visible][data-testid=submit-btn]提交按钮"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_visible_failure(self):
        page = _StubPage()
        page.set_element("data-testid=submit-btn", "提交按钮", visible=False)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[visible][data-testid=submit-btn]提交按钮"}
        with pytest.raises(VerificationError, match="可见性断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_element_not_found(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[visible][data-testid=missing]按钮"}
        with pytest.raises(VerificationError, match="可见性断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_with_ai_vision(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "visible": true, "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[visible]提交按钮",
            "target_element": "提交按钮",
        }
        await engine._execute_verify(action_info, step_id=1)


class TestNotVisibleAssertion:
    @pytest.mark.asyncio
    async def test_with_locator_not_visible_success(self):
        page = _StubPage()
        page.set_element("data-testid=loading", "加载中", visible=False)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[not_visible][data-testid=loading]加载中"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_with_locator_not_visible_failure(self):
        page = _StubPage()
        page.set_element("data-testid=loading", "加载中", visible=True)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[not_visible][data-testid=loading]加载中"}
        with pytest.raises(VerificationError, match="不可见断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_element_not_found_means_not_visible(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[not_visible][data-testid=nonexistent]不存在"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_with_ai_vision_not_visible(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "visible": false, "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[not_visible]加载中",
            "target_element": "加载中",
        }
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_without_locator_no_vision_model(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser, vision_model=None)
        action_info = {
            "text": "[not_visible]加载中",
            "target_element": "加载中",
        }
        with pytest.raises(VerificationError, match="需要AI视觉模型"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_wait_for_selector_exception_treated_as_not_visible(self):
        page = _StubPage()
        page.set_wait_for_selector_result(
            None, exception=TimeoutError("timeout")
        )
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[not_visible][data-testid=loading]加载中"}
        await engine._execute_verify(action_info, step_id=1)


# ============================================================
# URL 断言测试
# ============================================================


class TestUrlContainsAssertion:
    @pytest.mark.asyncio
    async def test_url_contains_success(self):
        browser = _make_browser_with_page("http://localhost:3000/home/project")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_contains]/home/project"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_url_contains_failure(self):
        browser = _make_browser_with_page("http://localhost:3000/login")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_contains]/home/project"}
        with pytest.raises(VerificationError, match="URL包含断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_url_contains_failure_shows_expected_and_actual(self):
        browser = _make_browser_with_page("http://localhost:3000/login")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_contains]/home/project"}
        with pytest.raises(VerificationError, match="期望包含 '/home/project'.*实际URL"):
            await engine._execute_verify(action_info, step_id=1)


class TestUrlEqualsAssertion:
    @pytest.mark.asyncio
    async def test_url_equals_success(self):
        browser = _make_browser_with_page("http://localhost:3000/login")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_equals]http://localhost:3000/login"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_url_equals_failure(self):
        browser = _make_browser_with_page("http://localhost:3000/home")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_equals]http://localhost:3000/login"}
        with pytest.raises(VerificationError, match="URL相等断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_url_equals_failure_shows_expected_and_actual(self):
        browser = _make_browser_with_page("http://localhost:3000/home")
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_equals]http://localhost:3000/login"}
        with pytest.raises(VerificationError, match="期望 'http://localhost:3000/login'.*实际URL"):
            await engine._execute_verify(action_info, step_id=1)


class TestUrlAssertionEdgeCases:
    @pytest.mark.asyncio
    async def test_url_assertion_page_not_initialized(self):
        browser = _StubBrowser(page=None)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[url_contains]/home"}
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# 回退 AI 视觉验证测试
# ============================================================


class TestFallbackToAiVision:
    @pytest.mark.asyncio
    async def test_non_structured_text_falls_back_to_ai_vision(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"passed": true, "reason": "验证通过"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {"text": "页面应显示登录按钮"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_non_structured_text_ai_vision_fails(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"passed": false, "reason": "未找到登录按钮"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {"text": "页面应显示登录按钮"}
        with pytest.raises(VerificationError, match="未找到登录按钮"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_non_structured_text_no_vision_model(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser, vision_model=None)
        action_info = {"text": "页面应显示登录按钮"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_empty_text_falls_back_to_ai_vision(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser, vision_model=None)
        action_info = {"text": ""}
        await engine._execute_verify(action_info, step_id=1)


# ============================================================
# 浏览器未初始化测试
# ============================================================


class TestBrowserNotInitialized:
    @pytest.mark.asyncio
    async def test_browser_none_raises_error(self):
        engine = _StubEngine(browser=None)
        action_info = {"text": "[text_contains][h1]标题"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_page_none_for_text_assertion(self):
        browser = _StubBrowser(page=None)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][h1]标题"}
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_page_none_for_visibility_assertion(self):
        browser = _StubBrowser(page=None)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[visible][h1]标题"}
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# AI 视觉定位（无定位器）测试
# ============================================================


class TestAiVisionTextAssertion:
    @pytest.mark.asyncio
    async def test_ai_vision_found_with_matching_text(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "text": "项目列表", "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[text_equals]项目列表",
            "target_element": "页面标题",
        }
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_ai_vision_found_with_non_matching_text(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "text": "用户管理", "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[text_equals]项目列表",
            "target_element": "页面标题",
        }
        with pytest.raises(VerificationError, match="文本相等断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_ai_vision_not_found(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": false, "reason": "未找到元素"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[text_contains]项目列表",
            "target_element": "页面标题",
        }
        with pytest.raises(VerificationError, match="AI视觉未找到元素"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_ai_vision_unparseable_response(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel("not a json response")
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[text_contains]项目列表",
            "target_element": "页面标题",
        }
        with pytest.raises(VerificationError, match="无法解析AI视觉定位结果"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_ai_vision_exception_returns_false_visibility(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)

        class FailingVision:
            def analyze_image(self, screenshot: bytes, prompt: str) -> str:
                raise RuntimeError("vision error")

        engine = _StubEngine(browser=browser, vision_model=FailingVision())
        action_info = {
            "text": "[not_visible]加载中",
            "target_element": "加载中",
        }
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_ai_vision_visible_with_unparseable_response(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel("not a json response")
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {
            "text": "[visible]提交按钮",
            "target_element": "提交按钮",
        }
        with pytest.raises(VerificationError, match="可见性断言失败"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# 结构化断言执行异常测试
# ============================================================


class TestStructuredAssertionExceptions:
    @pytest.mark.asyncio
    async def test_unparseable_syntax_raises_verification_error(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_invalid]something"}
        with pytest.raises(VerificationError, match="无法解析结构化断言语法"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_visibility_without_locator_uses_expected_as_fallback(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        vision = _StubVisionModel('{"found": true, "visible": true, "reason": "ok"}')
        engine = _StubEngine(browser=browser, vision_model=vision)
        action_info = {"text": "[visible]提交按钮"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_assertion_page_not_initialized(self):
        browser = _StubBrowser(page=None)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_equals][h1]标题"}
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_visibility_assertion_page_not_initialized(self):
        browser = _StubBrowser(page=None)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[visible][h1]标题"}
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# _execute_structured_assertion 直接调用测试
# ============================================================


class TestExecuteStructuredAssertionDirect:
    @pytest.mark.asyncio
    async def test_direct_call_with_text_contains(self):
        page = _StubPage()
        page.set_element("h1", "Hello World")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        await engine._execute_structured_assertion(
            "[text_contains][h1]Hello", {"text": "[text_contains][h1]Hello"}
        )

    @pytest.mark.asyncio
    async def test_direct_call_with_url_contains(self):
        browser = _make_browser_with_page("http://localhost:3000/home")
        engine = _StubEngine(browser=browser)
        await engine._execute_structured_assertion(
            "[url_contains]/home", {"text": "[url_contains]/home"}
        )

    @pytest.mark.asyncio
    async def test_direct_call_with_invalid_syntax(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        with pytest.raises(VerificationError, match="无法解析结构化断言语法"):
            await engine._execute_structured_assertion(
                "invalid syntax", {"text": "invalid syntax"}
            )
