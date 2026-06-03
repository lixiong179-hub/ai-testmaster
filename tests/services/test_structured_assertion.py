"""结构化断言单元测试

覆盖范围:
- 语法解析（各种格式）
- 文本断言（有/无定位器，contains/equals/matches，成功/失败）
- 可见性断言（有/无定位器，visible/not_visible，成功/失败）
- URL 断言（contains/equals，成功/失败）
- 回退 AI 视觉验证
- 断言失败时记录期望值与实际值
- 扩展断言：loading_visible/loading_hidden/response_time_lt/
  no_console_errors/no_network_errors/text_not_empty/no_sensitive_data/no_xss

要求: 不使用Mock，覆盖率>=95%
"""
import time

import pytest
from types import SimpleNamespace

from app.services.test_execution_engine.models import (
    StepExecutionError, VerificationError,
)
from app.services.test_execution_engine.structured_assertion_mixin import (
    StructuredAssertionMixin,
    _STRUCTURED_ASSERTION_PREFIXES,
    _ASSERTION_PATTERN,
    _EXTENDED_ASSERTION_PATTERN,
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
        self._is_visible_result: dict[str, bool] = {}
        self._wait_for_selector_state_result: dict[str, object] = {}
        self._wait_for_selector_state_exception: dict[str, Exception] = {}
        self._evaluate_result: list | None = []
        self._wait_for_load_state_result: Exception | None = None

    def set_element(self, selector: str, text: str = "", visible: bool = True):
        self._elements[selector] = _StubElement(text, visible)

    def set_wait_for_selector_result(self, result: object, exception: Exception | None = None):
        self._wait_for_selector_result = result
        self._wait_for_selector_exception = exception

    async def wait_for_selector(self, selector: str, timeout: int = 5000, state: str | None = None):
        if state == "hidden":
            exc = self._wait_for_selector_state_exception.get(selector)
            if exc:
                raise exc
            return self._wait_for_selector_state_result.get(selector, True)
        if self._wait_for_selector_exception:
            raise self._wait_for_selector_exception
        if self._wait_for_selector_result is not None:
            return self._wait_for_selector_result
        return self._elements.get(selector)

    async def is_visible(self, selector: str) -> bool:
        if selector in self._is_visible_result:
            return self._is_visible_result[selector]
        element = self._elements.get(selector)
        return bool(element and element._is_visible)

    async def wait_for_load_state(self, state: str, **kwargs) -> None:
        if self._wait_for_load_state_result:
            raise self._wait_for_load_state_result

    async def evaluate(self, expression: str) -> list | None:
        return self._evaluate_result


class _StubVisionModel:
    def __init__(self, response: str = '{"found": true, "text": "项目列表", "visible": true}'):
        self._response = response

    def analyze_image(self, screenshot: bytes, prompt: str) -> str:
        return self._response


class _StubBrowser:
    def __init__(self, page: _StubPage | None = None):
        self._page = page
        self._context = None
        self._defect_evidence: dict = {
            "console_errors": [],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        }

    @property
    def active_page(self):
        return self._page

    async def take_screenshot(self) -> bytes:
        return b"fake_screenshot"

    def get_defect_evidence(self) -> dict:
        return dict(self._defect_evidence)

    def clear_defect_evidence(self) -> None:
        self._defect_evidence = {
            "console_errors": [],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        }


class _StubEngine(StructuredAssertionMixin):
    def __init__(self, browser=None, vision_model=None):
        self.browser = browser
        self.vision_model = vision_model
        self._step_start_time_monotonic: float | None = None


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


# ============================================================
# 扩展断言前缀与模式匹配测试
# ============================================================


class TestExtendedAssertionPrefixes:
    def test_new_prefixes_in_structured_prefixes(self):
        prefixes = _STRUCTURED_ASSERTION_PREFIXES
        assert "[loading_visible" in prefixes
        assert "[loading_hidden" in prefixes
        assert "[response_time_lt" in prefixes
        assert "[no_console_errors" in prefixes
        assert "[no_network_errors" in prefixes
        assert "[text_not_empty" in prefixes
        assert "[no_sensitive_data" in prefixes
        assert "[no_xss" in prefixes

    def test_extended_pattern_matches_all_new_types(self):
        types = [
            "loading_visible", "loading_hidden", "response_time_lt",
            "no_console_errors", "no_network_errors", "text_not_empty",
            "no_sensitive_data", "no_xss",
        ]
        for t in types:
            match = _EXTENDED_ASSERTION_PATTERN.match(f"[{t}]value")
            assert match is not None, f"应匹配扩展断言类型: {t}"
            assert match.group(1) == t

    def test_extended_pattern_does_not_match_old_types(self):
        old_types = ["text_contains", "visible", "url_contains"]
        for t in old_types:
            match = _EXTENDED_ASSERTION_PATTERN.match(f"[{t}]value")
            assert match is None, f"扩展模式不应匹配旧类型: {t}"


class TestParseExtendedAssertionSyntax:
    def setup_method(self):
        self.engine = _StubEngine()

    def test_loading_visible_with_locator(self):
        result = self.engine._parse_extended_assertion_syntax(
            "[loading_visible][data-testid=loading]加载中"
        )
        assert result is not None
        assert result[0] == "loading_visible"
        assert result[1]["locator"] == "data-testid=loading"

    def test_loading_hidden_with_locator(self):
        result = self.engine._parse_extended_assertion_syntax(
            "[loading_hidden][data-testid=spinner]加载动画"
        )
        assert result is not None
        assert result[0] == "loading_hidden"
        assert result[1]["locator"] == "data-testid=spinner"

    def test_response_time_lt_with_threshold(self):
        result = self.engine._parse_extended_assertion_syntax("[response_time_lt]3000")
        assert result is not None
        assert result[0] == "response_time_lt"
        assert result[1]["threshold_ms"] == 3000

    def test_response_time_lt_invalid_threshold(self):
        with pytest.raises(VerificationError, match="阈值必须为正整数"):
            self.engine._parse_extended_assertion_syntax("[response_time_lt]abc")

    def test_response_time_lt_zero_threshold(self):
        with pytest.raises(VerificationError, match="阈值必须为正整数"):
            self.engine._parse_extended_assertion_syntax("[response_time_lt]0")

    def test_no_console_errors_no_exclude(self):
        result = self.engine._parse_extended_assertion_syntax("[no_console_errors]")
        assert result is not None
        assert result[0] == "no_console_errors"
        assert result[1].get("exclude_patterns") is None

    def test_no_console_errors_with_exclude(self):
        result = self.engine._parse_extended_assertion_syntax(
            "[no_console_errors]exclude:ResizeObserver,WebSocket"
        )
        assert result is not None
        assert result[0] == "no_console_errors"
        assert result[1]["exclude_patterns"] == ["ResizeObserver", "WebSocket"]

    def test_no_network_errors(self):
        result = self.engine._parse_extended_assertion_syntax("[no_network_errors]")
        assert result is not None
        assert result[0] == "no_network_errors"

    def test_text_not_empty_with_locator(self):
        result = self.engine._parse_extended_assertion_syntax(
            "[text_not_empty][data-testid=title]标题"
        )
        assert result is not None
        assert result[0] == "text_not_empty"
        assert result[1]["locator"] == "data-testid=title"

    def test_no_sensitive_data(self):
        result = self.engine._parse_extended_assertion_syntax("[no_sensitive_data]")
        assert result is not None
        assert result[0] == "no_sensitive_data"

    def test_no_xss(self):
        result = self.engine._parse_extended_assertion_syntax("[no_xss]")
        assert result is not None
        assert result[0] == "no_xss"

    def test_non_extended_returns_none(self):
        result = self.engine._parse_extended_assertion_syntax("[text_contains]hello")
        assert result is None


# ============================================================
# loading_visible / loading_hidden 断言测试
# ============================================================


class TestLoadingVisibleAssertion:
    @pytest.mark.asyncio
    async def test_loading_visible_success(self):
        page = _StubPage()
        page.set_element("data-testid=loading", "加载中", visible=True)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_visible][data-testid=loading]加载中"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_loading_visible_failure(self):
        page = _StubPage()
        page.set_element("data-testid=loading", "加载中", visible=False)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_visible][data-testid=loading]加载中"}
        with pytest.raises(VerificationError, match="加载指示器不可见"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_loading_visible_missing_locator(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_visible]"}
        with pytest.raises(VerificationError, match="缺少选择器"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_loading_visible_browser_exception(self):
        page = _StubPage()
        page._is_visible_result["data-testid=loading"] = True
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_visible][data-testid=loading]加载中"}
        await engine._execute_verify(action_info, step_id=1)


class TestLoadingHiddenAssertion:
    @pytest.mark.asyncio
    async def test_loading_hidden_success(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_hidden][data-testid=loading]加载中"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_loading_hidden_timeout_failure(self):
        page = _StubPage()
        page._wait_for_selector_state_exception["data-testid=loading"] = TimeoutError("timeout")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_hidden][data-testid=loading]加载中"}
        with pytest.raises(VerificationError, match="未在10秒内隐藏"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_loading_hidden_missing_locator(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_hidden]"}
        with pytest.raises(VerificationError, match="缺少选择器"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# response_time_lt 断言测试
# ============================================================


class TestResponseTimeLtAssertion:
    @pytest.mark.asyncio
    async def test_response_time_success(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        engine._step_start_time_monotonic = time.monotonic()
        action_info = {"text": "[response_time_lt]60000"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_response_time_failure_exceeded(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        engine._step_start_time_monotonic = time.monotonic() - 10
        action_info = {"text": "[response_time_lt]1000"}
        with pytest.raises(VerificationError, match="响应时间断言失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_response_time_failure_shows_actual_and_threshold(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        engine._step_start_time_monotonic = time.monotonic() - 5
        action_info = {"text": "[response_time_lt]1000"}
        with pytest.raises(VerificationError, match="实际耗时.*阈值 1000ms"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_response_time_no_start_time(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        engine._step_start_time_monotonic = None
        action_info = {"text": "[response_time_lt]3000"}
        with pytest.raises(VerificationError, match="步骤开始时间未记录"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_response_time_invalid_threshold(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[response_time_lt]abc"}
        with pytest.raises(VerificationError, match="阈值必须为正整数"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_response_time_networkidle_timeout(self):
        page = _StubPage()
        page._wait_for_load_state_result = TimeoutError("networkidle timeout")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        engine._step_start_time_monotonic = time.monotonic()
        action_info = {"text": "[response_time_lt]3000"}
        with pytest.raises(VerificationError, match="等待网络空闲超时"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# no_console_errors 断言测试
# ============================================================


class TestNoConsoleErrorsAssertion:
    @pytest.mark.asyncio
    async def test_no_console_errors_success(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_failure(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["console_errors"] = [
            {"type": "console_error", "message": "Uncaught TypeError", "source": "app.js:10"},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]"}
        with pytest.raises(VerificationError, match="控制台存在错误"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_with_exclude(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["console_errors"] = [
            {"type": "console_error", "message": "ResizeObserver loop limit exceeded", "source": ""},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]exclude:ResizeObserver"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_exclude_partial(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["console_errors"] = [
            {"type": "console_error", "message": "ResizeObserver loop limit exceeded", "source": ""},
            {"type": "console_error", "message": "Uncaught ReferenceError", "source": "app.js:5"},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]exclude:ResizeObserver"}
        with pytest.raises(VerificationError, match="Uncaught ReferenceError"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_multiple_excludes(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["console_errors"] = [
            {"type": "console_error", "message": "ResizeObserver loop", "source": ""},
            {"type": "console_error", "message": "WebSocket connection failed", "source": ""},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]exclude:ResizeObserver,WebSocket"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_without_browser(self):
        engine = _StubEngine(browser=None)
        action_info = {"text": "[no_console_errors]"}
        await engine._execute_verify(action_info, step_id=1)


# ============================================================
# no_network_errors 断言测试
# ============================================================


class TestNoNetworkErrorsAssertion:
    @pytest.mark.asyncio
    async def test_no_network_errors_success(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_network_errors]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_network_errors_failure(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["network_failures"] = [
            {"url": "https://api.example.com/users", "method": "GET", "status": 500, "duration_ms": 1200.0},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_network_errors]"}
        with pytest.raises(VerificationError, match="网络请求失败"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_network_errors_failure_shows_details(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        browser._defect_evidence["network_failures"] = [
            {"url": "https://api.example.com/data", "method": "POST", "status": 502, "duration_ms": 3000.0},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_network_errors]"}
        with pytest.raises(VerificationError, match="POST.*status=502"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# text_not_empty 断言测试
# ============================================================


class TestTextNotEmptyAssertion:
    @pytest.mark.asyncio
    async def test_text_not_empty_success(self):
        page = _StubPage()
        page.set_element("data-testid=title", "项目列表")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty][data-testid=title]标题"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_not_empty_failure_empty_string(self):
        page = _StubPage()
        page.set_element("data-testid=title", "")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty][data-testid=title]标题"}
        with pytest.raises(VerificationError, match="元素文本为空"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_not_empty_failure_whitespace(self):
        page = _StubPage()
        page.set_element("data-testid=title", "   \n\t  ")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty][data-testid=title]标题"}
        with pytest.raises(VerificationError, match="元素文本为空"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_not_empty_failure_none(self):
        page = _StubPage()
        element = _StubElement(text_content=None)
        page._elements["data-testid=title"] = element
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty][data-testid=title]标题"}
        with pytest.raises(VerificationError, match="元素文本为空"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_not_empty_missing_locator(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty]"}
        with pytest.raises(VerificationError, match="缺少选择器"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_text_not_empty_element_not_found(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_not_empty][data-testid=missing]标题"}
        with pytest.raises(VerificationError, match="未找到元素"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# no_sensitive_data 断言测试
# ============================================================


class TestNoSensitiveDataAssertion:
    @pytest.mark.asyncio
    async def test_no_sensitive_data_success(self):
        page = _StubPage()
        page._evaluate_result = []
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_password_plaintext(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "password_plaintext", "detail": "input[type=password] contains non-mask value"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*password_plaintext"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_jwt_token(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "jwt_token", "detail": "JWT token pattern (eyJ) found in page text"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*jwt_token"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_api_key(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "api_key", "detail": "API key pattern (sk-) found in page text"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*api_key"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_phone_number(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "phone_number", "detail": "Chinese phone number pattern found in page text"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*phone_number"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_id_card(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "id_card", "detail": "ID card number pattern found in page text"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*id_card"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_network_sensitive_url(self):
        page = _StubPage()
        page._evaluate_result = []
        browser = _StubBrowser(page=page)
        browser._defect_evidence["network_failures"] = [
            {"url": "https://api.example.com/token/refresh", "method": "POST", "status": 500, "duration_ms": 100.0},
        ]
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="敏感数据暴露.*sensitive_in_network"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_marks_p0(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "jwt_token", "detail": "JWT token found"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="\\[P0\\]"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_evaluate_exception(self):
        page = _StubPage()
        page._evaluate_result = None
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_multiple_findings(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "jwt_token", "detail": "JWT found"},
            {"type": "api_key", "detail": "API key found"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        with pytest.raises(VerificationError, match="jwt_token.*api_key"):
            await engine._execute_verify(action_info, step_id=1)


# ============================================================
# no_xss 断言测试
# ============================================================


class TestNoXssAssertion:
    @pytest.mark.asyncio
    async def test_no_xss_success(self):
        page = _StubPage()
        page._evaluate_result = []
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_script_alert_detected(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "xss_payload", "detail": "XSS pattern 'script_alert' detected in DOM"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        with pytest.raises(VerificationError, match="XSS漏洞检测.*script_alert"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_img_onerror_detected(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "xss_payload", "detail": "XSS pattern 'img_onerror' detected in DOM"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        with pytest.raises(VerificationError, match="XSS漏洞检测.*img_onerror"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_svg_onload_detected(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "xss_payload", "detail": "XSS pattern 'svg_onload' detected in DOM"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        with pytest.raises(VerificationError, match="XSS漏洞检测.*svg_onload"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_javascript_uri_detected(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "xss_payload", "detail": "XSS pattern 'javascript_uri' detected in DOM"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        with pytest.raises(VerificationError, match="XSS漏洞检测.*javascript_uri"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_multiple_patterns(self):
        page = _StubPage()
        page._evaluate_result = [
            {"type": "xss_payload", "detail": "XSS pattern 'script_alert' detected in DOM"},
            {"type": "xss_payload", "detail": "XSS pattern 'img_onerror' detected in DOM"},
        ]
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        with pytest.raises(VerificationError, match="script_alert.*img_onerror"):
            await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_evaluate_returns_none(self):
        page = _StubPage()
        page._evaluate_result = None
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        await engine._execute_verify(action_info, step_id=1)


# ============================================================
# 扩展断言通过 _execute_verify 入口集成测试
# ============================================================


class TestExtendedAssertionViaExecuteVerify:
    @pytest.mark.asyncio
    async def test_loading_visible_routed_correctly(self):
        page = _StubPage()
        page.set_element("data-testid=spinner", "加载中", visible=True)
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[loading_visible][data-testid=spinner]加载中"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_console_errors_routed_correctly(self):
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_console_errors]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_sensitive_data_routed_correctly(self):
        page = _StubPage()
        page._evaluate_result = []
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_sensitive_data]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_no_xss_routed_correctly(self):
        page = _StubPage()
        page._evaluate_result = []
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[no_xss]"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_old_assertions_still_work(self):
        """确保扩展断言不影响原有断言功能。"""
        page = _StubPage()
        page.set_element("h1", "Hello World")
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser)
        action_info = {"text": "[text_contains][h1]Hello"}
        await engine._execute_verify(action_info, step_id=1)

    @pytest.mark.asyncio
    async def test_non_structured_still_falls_back(self):
        """非结构化文本仍回退到AI视觉验证。"""
        page = _StubPage()
        browser = _StubBrowser(page=page)
        engine = _StubEngine(browser=browser, vision_model=None)
        action_info = {"text": "页面应显示登录按钮"}
        await engine._execute_verify(action_info, step_id=1)


# ============================================================
# _get_defect_evidence 边界测试
# ============================================================


class TestGetDefectEvidence:
    @pytest.mark.asyncio
    async def test_browser_without_get_defect_evidence(self):
        """browser 没有 get_defect_evidence 方法时返回空结构。"""
        page = _StubPage()

        class MinimalBrowser:
            active_page = page

        engine = _StubEngine(browser=MinimalBrowser())
        evidence = engine._get_defect_evidence()
        assert evidence["console_errors"] == []
        assert evidence["network_failures"] == []

    @pytest.mark.asyncio
    async def test_browser_none_returns_empty(self):
        engine = _StubEngine(browser=None)
        evidence = engine._get_defect_evidence()
        assert evidence["console_errors"] == []
        assert evidence["network_failures"] == []

    @pytest.mark.asyncio
    async def test_get_defect_evidence_exception_returns_empty(self):
        page = _StubPage()

        class BrokenBrowser:
            active_page = page

            def get_defect_evidence(self):
                raise RuntimeError("broken")

        engine = _StubEngine(browser=BrokenBrowser())
        evidence = engine._get_defect_evidence()
        assert evidence["console_errors"] == []
