"""SPA路由导航支持单元测试（History模式）

测试范围:
- 完整URL导航（保持现有行为）
- 相对路径导航（/home/project）
- 菜单点击导航（target_element为CSS选择器）
- base_url拼接正确性
- 无URL且无target_element时抛异常
- _extract_relative_path 方法
- _get_base_url 方法
- _is_css_selector 方法

要求: 不使用Mock，覆盖率>=95%
"""
import pytest
from types import SimpleNamespace

from app.services.test_execution_engine.models import (
    ActionType, StepExecutionError,
)
from app.services.test_execution_engine.action_executor_basic_mixin import (
    ActionExecutorBasicMixin,
)


class _StubEngine(ActionExecutorBasicMixin):

    def __init__(self, browser=None, precondition_service=None):
        self.browser = browser
        self.precondition_service = precondition_service


def _make_async_return(value):
    async def _return(*args, **kwargs):
        return value
    return _return


async def _noop(*args, **kwargs):
    pass


class TestExtractRelativePath:
    """_extract_relative_path 方法测试"""

    def setup_method(self):
        self.engine = _StubEngine()

    def test_simple_path(self):
        result = self.engine._extract_relative_path("导航到 /home/project")
        assert result == "/home/project"

    def test_path_at_start(self):
        result = self.engine._extract_relative_path("/login")
        assert result == "/login"

    def test_nested_path(self):
        result = self.engine._extract_relative_path("访问 /home/project/list")
        assert result == "/home/project/list"

    def test_no_relative_path(self):
        result = self.engine._extract_relative_path("导航到首页")
        assert result is None

    def test_full_url_not_matched(self):
        result = self.engine._extract_relative_path("访问 https://example.com/home")
        assert result is None

    def test_empty_text(self):
        result = self.engine._extract_relative_path("")
        assert result is None

    def test_multiple_paths_returns_first(self):
        result = self.engine._extract_relative_path("/home /project")
        assert result == "/home"

    def test_path_with_hyphen(self):
        result = self.engine._extract_relative_path("打开 /user-profile/settings")
        assert result == "/user-profile/settings"


class TestGetBaseUrl:
    """_get_base_url 方法测试"""

    def test_with_precondition_service_and_url(self):
        testObjInfo = SimpleNamespace(url="https://example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(precondition_service=precondition)
        assert engine._get_base_url() == "https://example.com"

    def test_with_precondition_service_no_url(self):
        testObjInfo = SimpleNamespace(url=None)
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(precondition_service=precondition)
        assert engine._get_base_url() is None

    def test_with_precondition_service_no_test_object_info(self):
        precondition = SimpleNamespace(test_object_info=None)
        engine = _StubEngine(precondition_service=precondition)
        assert engine._get_base_url() is None

    def test_no_precondition_service(self):
        engine = _StubEngine(precondition_service=None)
        assert engine._get_base_url() is None

    def test_no_precondition_service_attr(self):
        engine = _StubEngine()
        assert engine._get_base_url() is None


class TestIsCssSelector:
    """_is_css_selector 方法测试"""

    def setup_method(self):
        self.engine = _StubEngine()

    def test_id_selector(self):
        assert self.engine._is_css_selector("#nav-home") is True

    def test_class_selector(self):
        assert self.engine._is_css_selector(".menu-item") is True

    def test_attribute_selector(self):
        assert self.engine._is_css_selector("[data-route='/home']") is True

    def test_tag_with_class(self):
        assert self.engine._is_css_selector("a.menu-link") is True

    def test_tag_with_id(self):
        assert self.engine._is_css_selector("div#content") is True

    def test_tag_with_attribute(self):
        assert self.engine._is_css_selector("a[href='/home']") is True

    def test_plain_text_not_selector(self):
        assert self.engine._is_css_selector("首页") is False

    def test_url_not_selector(self):
        assert self.engine._is_css_selector("https://example.com") is False

    def test_empty_string(self):
        assert self.engine._is_css_selector("") is False

    def test_none_equivalent(self):
        assert self.engine._is_css_selector(None) is False

    def test_relative_path_not_selector(self):
        assert self.engine._is_css_selector("/home/project") is False

    def test_plain_tag_name_not_selector(self):
        assert self.engine._is_css_selector("div") is False


class TestExecuteNavigateFullUrl:
    """完整URL导航测试（保持现有行为）"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_navigate({"text": "导航到 https://example.com"})

    @pytest.mark.asyncio
    async def test_full_url_navigation(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url
            navigated["wait_until"] = wait_until

        browser = SimpleNamespace(navigate=mock_navigate)
        engine = _StubEngine(browser=browser)
        await engine._execute_navigate({"text": "导航到 https://example.com/home"})
        assert navigated["url"] == "https://example.com/home"

    @pytest.mark.asyncio
    async def test_http_url_navigation(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        engine = _StubEngine(browser=browser)
        await engine._execute_navigate({"text": "访问 http://localhost:3000"})
        assert navigated["url"] == "http://localhost:3000"


class TestExecuteNavigateRelativePath:
    """相对路径导航测试（SPA History模式）"""

    @pytest.mark.asyncio
    async def test_relative_path_with_base_url(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url
            navigated["wait_until"] = wait_until

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "导航到 /home/project"})
        assert navigated["url"] == "https://example.com/home/project"
        assert navigated["wait_until"] == "networkidle"

    @pytest.mark.asyncio
    async def test_relative_path_base_url_trailing_slash(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://example.com/")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "访问 /login"})
        assert navigated["url"] == "https://example.com/login"

    @pytest.mark.asyncio
    async def test_relative_path_without_base_url(self):
        browser = SimpleNamespace(navigate=_noop)
        engine = _StubEngine(browser=browser, precondition_service=None)
        with pytest.raises(StepExecutionError, match="相对路径导航需要base_url"):
            await engine._execute_navigate({"text": "导航到 /home/project"})

    @pytest.mark.asyncio
    async def test_relative_path_base_url_none(self):
        browser = SimpleNamespace(navigate=_noop)
        testObjInfo = SimpleNamespace(url=None)
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        with pytest.raises(StepExecutionError, match="相对路径导航需要base_url"):
            await engine._execute_navigate({"text": "打开 /settings"})

    @pytest.mark.asyncio
    async def test_spa_route_home_project(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://test-app.example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/home/project"})
        assert navigated["url"] == "https://test-app.example.com/home/project"

    @pytest.mark.asyncio
    async def test_spa_route_login(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://test-app.example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/login"})
        assert navigated["url"] == "https://test-app.example.com/login"


class TestExecuteNavigateCssSelector:
    """菜单点击导航测试（target_element为CSS选择器）"""

    @pytest.mark.asyncio
    async def test_css_selector_click_navigation(self):
        clicked = {}

        async def mock_click(selector):
            clicked["selector"] = selector

        async def mock_wait_for_load_state(state):
            clicked["load_state"] = state

        page = SimpleNamespace(
            click=mock_click,
            wait_for_load_state=mock_wait_for_load_state,
        )
        browser = SimpleNamespace(_page=page, active_page=page, navigate=_noop)
        engine = _StubEngine(browser=browser)
        await engine._execute_navigate({
            "text": "点击菜单导航",
            "target_element": "#nav-home",
        })
        assert clicked["selector"] == "#nav-home"
        assert clicked["load_state"] == "networkidle"

    @pytest.mark.asyncio
    async def test_class_selector_click_navigation(self):
        clicked = {}

        async def mock_click(selector):
            clicked["selector"] = selector

        async def mock_wait_for_load_state(state):
            pass

        page = SimpleNamespace(
            click=mock_click,
            wait_for_load_state=mock_wait_for_load_state,
        )
        browser = SimpleNamespace(_page=page, active_page=page, navigate=_noop)
        engine = _StubEngine(browser=browser)
        await engine._execute_navigate({
            "text": "菜单导航",
            "target_element": ".menu-item-project",
        })
        assert clicked["selector"] == ".menu-item-project"

    @pytest.mark.asyncio
    async def test_attribute_selector_click_navigation(self):
        clicked = {}

        async def mock_click(selector):
            clicked["selector"] = selector

        async def mock_wait_for_load_state(state):
            pass

        page = SimpleNamespace(
            click=mock_click,
            wait_for_load_state=mock_wait_for_load_state,
        )
        browser = SimpleNamespace(_page=page, active_page=page, navigate=_noop)
        engine = _StubEngine(browser=browser)
        await engine._execute_navigate({
            "text": "菜单导航",
            "target_element": "[data-route='/home']",
        })
        assert clicked["selector"] == "[data-route='/home']"

    @pytest.mark.asyncio
    async def test_css_selector_page_not_initialized(self):
        browser = SimpleNamespace(_page=None, active_page=None, navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_navigate({
                "text": "菜单导航",
                "target_element": "#nav-home",
            })

    @pytest.mark.asyncio
    async def test_css_selector_click_failure(self):
        async def mock_click(selector):
            raise RuntimeError("element not found")

        async def mock_wait_for_load_state(state):
            pass

        page = SimpleNamespace(
            click=mock_click,
            wait_for_load_state=mock_wait_for_load_state,
        )
        browser = SimpleNamespace(_page=page, active_page=page, navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="点击导航菜单项失败"):
            await engine._execute_navigate({
                "text": "菜单导航",
                "target_element": "#nonexistent",
            })

    @pytest.mark.asyncio
    async def test_non_css_selector_target_element_ignored(self):
        browser = SimpleNamespace(navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="无法从动作中提取URL或路径"):
            await engine._execute_navigate({
                "text": "随便导航",
                "target_element": "首页",
            })


class TestExecuteNavigateNoTarget:
    """无URL且无target_element时抛异常"""

    @pytest.mark.asyncio
    async def test_no_url_no_path_no_selector(self):
        browser = SimpleNamespace(navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="无法从动作中提取URL或路径"):
            await engine._execute_navigate({"text": "导航到首页"})

    @pytest.mark.asyncio
    async def test_empty_text(self):
        browser = SimpleNamespace(navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="无法从动作中提取URL或路径"):
            await engine._execute_navigate({"text": ""})

    @pytest.mark.asyncio
    async def test_text_without_navigable_target(self):
        browser = SimpleNamespace(navigate=_noop)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="无法从动作中提取URL或路径"):
            await engine._execute_navigate({"text": "点击确认按钮"})


class TestBaseUrlConcatenation:
    """base_url拼接正确性测试"""

    @pytest.mark.asyncio
    async def test_base_url_without_trailing_slash_path_without_double_slash(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/home/project"})
        assert navigated["url"] == "https://example.com/home/project"
        assert "//home" not in navigated["url"].replace("https://", "")

    @pytest.mark.asyncio
    async def test_base_url_with_trailing_slash(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://example.com/")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/home/project"})
        assert navigated["url"] == "https://example.com/home/project"

    @pytest.mark.asyncio
    async def test_base_url_with_port(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="http://localhost:3000")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/login"})
        assert navigated["url"] == "http://localhost:3000/login"

    @pytest.mark.asyncio
    async def test_deep_nested_path(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://app.example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({"text": "/home/project/case/detail"})
        assert navigated["url"] == "https://app.example.com/home/project/case/detail"


class TestNavigatePriority:
    """导航优先级测试：完整URL > 相对路径 > CSS选择器"""

    @pytest.mark.asyncio
    async def test_full_url_takes_priority_over_relative_path(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://other.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({
            "text": "导航到 https://target.com/page /home/fallback",
        })
        assert navigated["url"] == "https://target.com/page"

    @pytest.mark.asyncio
    async def test_relative_path_takes_priority_over_css_selector(self):
        navigated = {}

        async def mock_navigate(url, wait_until="load"):
            navigated["url"] = url

        browser = SimpleNamespace(navigate=mock_navigate)
        testObjInfo = SimpleNamespace(url="https://example.com")
        precondition = SimpleNamespace(test_object_info=testObjInfo)
        engine = _StubEngine(browser=browser, precondition_service=precondition)
        await engine._execute_navigate({
            "text": "导航到 /home/project",
            "target_element": "#nav-home",
        })
        assert navigated["url"] == "https://example.com/home/project"
