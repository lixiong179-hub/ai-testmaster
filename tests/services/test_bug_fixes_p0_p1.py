"""Bug修复单元测试 - 覆盖3个P0/P1级Bug修复的验证。

修复1: switch_frame frame引用丢失 (P0)
修复2: 密码存储混乱 (P0)
修复3: execute_script安全校验 (P1)

要求: 不使用Mock，覆盖率>=95%
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.test_execution_engine.action_executor_basic_mixin import (
    ActionExecutorBasicMixin,
)
from app.services.test_execution_engine.models import (
    StepExecutionError,
)
from app.utils.browser_controller_base import BrowserControllerV2, BrowserConfig


# ============================================================
# 修复1: switch_frame frame引用丢失
# ============================================================


class _StubFrame:
    def __init__(self, name: str = "test_frame"):
        self._name = name


class _StubPage:
    def __init__(self, url: str = "http://localhost:3000"):
        self.url = url
        self._frames = {}
        self._frame_locators = {}

    def add_frame(self, name: str, frame: _StubFrame) -> None:
        self._frames[name] = frame

    def add_frame_locator(self, selector: str, frame: _StubFrame) -> None:
        self._frame_locators[selector] = frame

    def frame(self, name: str = None, url: str = None):
        if name and name in self._frames:
            return self._frames[name]
        return None

    def frame_locator(self, selector: str):
        return self._frame_locators.get(selector)


class _StubContext:
    def __init__(self, pages=None):
        self.pages = pages or []


class _StubBrowserController(BrowserControllerV2):
    def __init__(self):
        self.config = BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._current_frame = None
        self._is_initialized = True
        self._window_size_fixed = False
        self._last_screenshot_time = 0
        self._screenshot_cache = None


class _StubEngine(ActionExecutorBasicMixin):
    def __init__(self, browser=None):
        self.browser = browser


class TestBrowserControllerFrameSupport:
    """BrowserControllerV2 frame切换支持测试"""

    def test_initial_current_frame_is_none(self) -> None:
        ctrl = _StubBrowserController()
        assert ctrl._current_frame is None

    def test_active_page_returns_page_when_no_frame(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        assert ctrl.active_page is stub_page

    def test_active_page_returns_frame_when_set(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        assert ctrl.active_page is frame
        assert ctrl.active_page is not stub_page

    def test_switch_to_main_resets_frame(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        assert ctrl.active_page is frame
        ctrl.switch_to_main()
        assert ctrl.active_page is stub_page
        assert ctrl._current_frame is None

    def test_close_clears_current_frame(self) -> None:
        ctrl = _StubBrowserController()
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        assert ctrl._current_frame is not None
        ctrl._current_frame = None
        ctrl._page = None
        assert ctrl._current_frame is None


class TestSwitchFrameExecution:
    """_execute_switch_frame 执行测试"""

    @pytest.mark.asyncio
    async def test_switch_to_frame_saves_reference(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        frame = _StubFrame("myframe")
        stub_page.add_frame("myframe", frame)
        ctrl._page = stub_page
        engine = _StubEngine(browser=ctrl)

        step = SimpleNamespace(target_element="myframe")
        await engine._execute_switch_frame({"text": "myframe"}, step)

        assert ctrl._current_frame is frame
        assert ctrl.active_page is frame

    @pytest.mark.asyncio
    async def test_switch_to_main_keyword(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        assert ctrl._current_frame is not None
        engine = _StubEngine(browser=ctrl)

        for keyword in ["main", "default", "top", "Main", "DEFAULT", "TOP"]:
            ctrl.switch_to_frame(frame)
            assert ctrl._current_frame is not None
            step = SimpleNamespace(target_element=keyword)
            await engine._execute_switch_frame({"text": keyword}, step)
            assert ctrl._current_frame is None
            assert ctrl.active_page is stub_page

    @pytest.mark.asyncio
    async def test_switch_to_main_empty_target(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        engine = _StubEngine(browser=ctrl)

        step = SimpleNamespace(target_element="")
        await engine._execute_switch_frame({"text": ""}, step)
        assert ctrl._current_frame is None

    @pytest.mark.asyncio
    async def test_switch_frame_by_css_selector(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        frame = _StubFrame("#myIframe")
        stub_page.add_frame_locator("#myIframe", frame)
        ctrl._page = stub_page
        engine = _StubEngine(browser=ctrl)

        step = SimpleNamespace(target_element="#myIframe")
        await engine._execute_switch_frame({"text": "#myIframe"}, step)
        assert ctrl._current_frame is frame

    @pytest.mark.asyncio
    async def test_switch_frame_not_found_raises(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        engine = _StubEngine(browser=ctrl)

        step = SimpleNamespace(target_element="nonexistent_frame")
        with pytest.raises(StepExecutionError, match="未找到目标iframe"):
            await engine._execute_switch_frame({"text": "nonexistent_frame"}, step)

    @pytest.mark.asyncio
    async def test_switch_frame_no_browser_raises(self) -> None:
        engine = _StubEngine(browser=None)
        step = SimpleNamespace(target_element="myframe")
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_switch_frame({"text": "myframe"}, step)

    @pytest.mark.asyncio
    async def test_switch_frame_no_page_raises(self) -> None:
        ctrl = _StubBrowserController()
        ctrl._page = None
        engine = _StubEngine(browser=ctrl)
        step = SimpleNamespace(target_element="myframe")
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_switch_frame({"text": "myframe"}, step)


class TestActivePageUsage:
    """验证 action_executor_basic_mixin 使用 active_page"""

    @pytest.mark.asyncio
    async def test_execute_script_uses_active_page(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        engine = _StubEngine(browser=ctrl)

        assert ctrl.active_page is frame
        assert ctrl.active_page is not stub_page

    @pytest.mark.asyncio
    async def test_upload_uses_active_page(self) -> None:
        ctrl = _StubBrowserController()
        stub_page = _StubPage()
        ctrl._page = stub_page
        frame = _StubFrame("myframe")
        ctrl.switch_to_frame(frame)
        engine = _StubEngine(browser=ctrl)

        assert ctrl.active_page is frame


# ============================================================
# 修复2: 密码存储混乱
# ============================================================


class TestSelfTestPasswordNotInEnvConfigs:
    """web_env_configs 不存储密码"""

    def test_env_configs_no_password_key(self) -> None:
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
        }, clear=False):
            from app.services.self_test_service import _get_self_test_env_configs
            configs = _get_self_test_env_configs()
            assert "password" not in configs["test"]

    async def test_password_stored_via_test_object_password(self, testUser, sync_backed_async_db) -> None:
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "my_secret_pass",
        }, clear=False):
            from app.services.self_test_service import create_self_test_project
            project = await create_self_test_project(sync_backed_async_db, testUser.id)

        web_configs = json.loads(project.web_env_configs)
        assert "password" not in web_configs["test"]

        assert project.test_object_password == "my_secret_pass"

    async def test_password_encrypted_in_db_column(self, testUser, sync_backed_async_db) -> None:
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "my_secret_pass",
        }, clear=False):
            from app.services.self_test_service import create_self_test_project
            project = await create_self_test_project(sync_backed_async_db, testUser.id)

        assert project.test_object_password_encrypted is not None
        assert project.test_object_password_encrypted != "my_secret_pass"
        assert project.test_object_password_encrypted.startswith("gAAAAA")

    async def test_no_password_env_stores_none(self, testUser, sync_backed_async_db) -> None:
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "",
        }, clear=False):
            from app.services.self_test_service import create_self_test_project
            project = await create_self_test_project(sync_backed_async_db, testUser.id)

        assert project.test_object_password is None
        assert project.test_object_password_encrypted is None


class TestTestObjectInfoPasswordResolution:
    """test_object_mixin 密码解析不再双重解密"""

    @pytest.mark.asyncio
    async def test_password_from_test_object_property_not_decrypted_again(self) -> None:
        from app.services.precondition.test_object_mixin import TestObjectInfoMixin
        from app.models.project import Project

        mixin = TestObjectInfoMixin()

        project = Project(
            name="test_pwd_project",
            user_id=1,
            status=1,
            project_type="web",
            test_object_type="web",
            test_object_url="http://localhost:5173",
            test_object_username="admin",
        )
        project.test_object_password = "plain_password"

        info = await mixin.read_test_object_info(project)
        assert info.password == "plain_password"

    @pytest.mark.asyncio
    async def test_password_from_env_config_decrypted(self) -> None:
        from app.services.precondition.test_object_mixin import TestObjectInfoMixin
        from app.models.project import Project
        from app.utils.crypto import encrypt_password

        mixin = TestObjectInfoMixin()

        encrypted = encrypt_password("env_password")
        env_config = {
            "url": "http://localhost:5173",
            "username": "admin",
            "password": encrypted,
        }

        project = Project(
            name="test_env_pwd_project",
            user_id=1,
            status=1,
            project_type="web",
            test_object_type="web",
            test_object_url="http://localhost:5173",
            test_object_username="admin",
        )

        info = await mixin.read_test_object_info(project, env_config=env_config)
        assert info.password == "env_password"

    @pytest.mark.asyncio
    async def test_no_password_returns_none(self) -> None:
        from app.services.precondition.test_object_mixin import TestObjectInfoMixin
        from app.models.project import Project

        mixin = TestObjectInfoMixin()

        project = Project(
            name="test_no_pwd_project",
            user_id=1,
            status=1,
            project_type="web",
            test_object_type="web",
            test_object_url="http://localhost:5173",
            test_object_username="admin",
        )

        info = await mixin.read_test_object_info(project)
        assert info.password is None


# ============================================================
# 修复3: execute_script安全校验
# ============================================================


class TestScriptSafetyValidation:
    """_validate_script_safety 安全校验测试"""

    def setup_method(self) -> None:
        self.engine = _StubEngine()

    def test_safe_script_returns_true(self) -> None:
        assert self.engine._validate_script_safety("document.querySelector('.btn').click()") is True

    def test_safe_script_simple_return(self) -> None:
        assert self.engine._validate_script_safety("return 1 + 1") is True

    def test_while_true_detected(self) -> None:
        assert self.engine._validate_script_safety("while(true) { break; }") is False

    def test_while_True_detected(self) -> None:
        assert self.engine._validate_script_safety("while(True) { break; }") is False

    def test_for_ever_detected(self) -> None:
        assert self.engine._validate_script_safety("for(;;) { break; }") is False

    def test_document_cookie_detected(self) -> None:
        assert self.engine._validate_script_safety("var c = document.cookie") is False

    def test_window_location_assignment_detected(self) -> None:
        assert self.engine._validate_script_safety("window.location = 'http://evil.com'") is False

    def test_window_location_read_is_safe(self) -> None:
        assert self.engine._validate_script_safety("var url = window.location.href") is True

    def test_xmlhttprequest_detected(self) -> None:
        assert self.engine._validate_script_safety("var xhr = new XMLHttpRequest()") is False

    def test_fetch_detected(self) -> None:
        assert self.engine._validate_script_safety("fetch('/api/data')") is False

    def test_eval_detected(self) -> None:
        assert self.engine._validate_script_safety("eval('alert(1)')") is False

    def test_new_function_detected(self) -> None:
        assert self.engine._validate_script_safety("new Function('return 1')()") is False

    def test_multiple_dangers_detected(self) -> None:
        script = "while(true) { eval('fetch(document.cookie)'); }"
        assert self.engine._validate_script_safety(script) is False

    def test_empty_script_is_safe(self) -> None:
        assert self.engine._validate_script_safety("") is True

    def test_case_insensitive_while_true(self) -> None:
        assert self.engine._validate_script_safety("while(TRUE) {}") is False

    def test_fetch_in_string_not_detected(self) -> None:
        assert self.engine._validate_script_safety("var s = 'use fetch to get data'") is True
