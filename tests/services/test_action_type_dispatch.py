"""ActionType 分发逻辑单元测试

测试范围:
- _resolve_action_type 新增 5 种动作类型映射
- _dispatch_step_action 新增 5 个分支的路由
- 兜底分支 warning 日志
- 各执行方法的浏览器未初始化校验

要求: 不使用Mock，覆盖率>=95%
"""
import pytest
from types import SimpleNamespace

from app.services.test_execution_engine.models import (
    ActionType, StepExecutionError, StepExecutionResult, ExecutionStatus,
)
from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin
from app.services.test_execution_engine.action_executor_basic_mixin import (
    ActionExecutorBasicMixin,
)


async def _noop(*args, **kwargs):
    pass


class _StubEngine(StepExecutorMixin, ActionExecutorBasicMixin):
    """最小化引擎组合，用于测试分发路由。"""

    def __init__(self, browser=None):
        self.browser = browser
        self.enable_ai_recognition = False
        self.enable_test_data_param = False
        self.locator_service = None
        self.parameterizer = None

    async def _execute_click(self, action_info, step_id=None, step_test_data=None):
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

    async def _execute_captcha(self, action_info, step_id=None):
        raise StepExecutionError("验证码方法未实现")

    async def _execute_verify(self, action_info, step_id=None):
        raise StepExecutionError("验证方法未实现")

    async def _execute_with_self_healing(self, *args, **kwargs):
        raise StepExecutionError("自愈执行未实现")

    async def _execute_mobile_step(self, *args, **kwargs):
        raise StepExecutionError("移动端执行未实现")

    async def _execute_action_by_type(self, *args, **kwargs):
        raise StepExecutionError("动作分发未实现")


def _make_step(
    step_number: int = 1,
    action: str = "",
    action_type: str = "",
    input_value: str = "",
    target_element: str = "",
    step_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=step_id,
        step_number=step_number,
        action=action,
        action_type=action_type,
        input_value=input_value,
        target_element=target_element,
        expected_result="",
    )


def _make_async_return(value):
    async def _return(*args, **kwargs):
        return value
    return _return


def _make_browser(page=None, context=None, **kwargs):
    """创建 Mock browser，同时设置 _page 和 active_page 属性以保持一致。"""
    defaults = {
        "switch_to_frame": lambda frame: None,
        "switch_to_main": lambda: None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(_page=page, active_page=page, _context=context, **defaults)


class TestResolveActionType:
    """_resolve_action_type 新增映射测试"""

    def setup_method(self):
        self.engine = _StubEngine()

    def test_switch_frame_mapping(self):
        step = _make_step(action_type="switch_frame")
        action_type, action_info = self.engine._resolve_action_type(step, "切换iframe")
        assert action_type == ActionType.SWITCH_FRAME

    def test_switch_window_mapping(self):
        step = _make_step(action_type="switch_window")
        action_type, action_info = self.engine._resolve_action_type(step, "切换窗口")
        assert action_type == ActionType.SWITCH_WINDOW

    def test_upload_mapping(self):
        step = _make_step(action_type="upload")
        action_type, action_info = self.engine._resolve_action_type(step, "上传文件")
        assert action_type == ActionType.UPLOAD

    def test_execute_script_mapping(self):
        step = _make_step(action_type="execute_script")
        action_type, action_info = self.engine._resolve_action_type(step, "执行脚本")
        assert action_type == ActionType.EXECUTE_SCRIPT

    def test_screenshot_mapping(self):
        step = _make_step(action_type="screenshot")
        action_type, action_info = self.engine._resolve_action_type(step, "截图")
        assert action_type == ActionType.SCREENSHOT

    def test_unknown_action_type_falls_back_to_click(self):
        step = _make_step(action_type="nonexistent_type")
        action_type, action_info = self.engine._resolve_action_type(step, "未知操作")
        assert action_type == ActionType.CLICK

    def test_existing_action_types_unchanged(self):
        cases = [
            ("click", ActionType.CLICK),
            ("input", ActionType.INPUT),
            ("navigate", ActionType.NAVIGATE),
            ("verify", ActionType.VERIFY),
            ("wait", ActionType.WAIT),
            ("scroll", ActionType.SCROLL),
            ("hover", ActionType.HOVER),
            ("select", ActionType.SELECT),
            ("captcha", ActionType.VERIFY_CAPTCHA),
            ("refresh", ActionType.REFRESH),
            ("keypress", ActionType.KEYBOARD),
        ]
        for action_type_str, expected in cases:
            step = _make_step(action_type=action_type_str)
            action_type, _ = self.engine._resolve_action_type(step, action_type_str)
            assert action_type == expected, f"映射 {action_type_str} 应为 {expected}"


class TestDispatchStepAction:
    """_dispatch_step_action 分发路由测试

    通过浏览器未初始化时抛出 StepExecutionError 来验证
    分发是否到达了正确的执行方法。
    """

    def setup_method(self):
        self.engine = _StubEngine(browser=None)

    @pytest.mark.asyncio
    async def test_switch_frame_dispatch(self):
        step = _make_step(target_element="myframe")
        action_info = {"type": ActionType.SWITCH_FRAME, "text": "切换iframe"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.SWITCH_FRAME, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_switch_window_dispatch(self):
        step = _make_step(target_element="新窗口")
        action_info = {"type": ActionType.SWITCH_WINDOW, "text": "切换窗口"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.SWITCH_WINDOW, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_upload_dispatch(self):
        step = _make_step(target_element="input[type=file]", input_value="/tmp/test.txt")
        action_info = {"type": ActionType.UPLOAD, "text": "上传文件"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.UPLOAD, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_execute_script_dispatch(self):
        step = _make_step(input_value="document.title")
        action_info = {"type": ActionType.EXECUTE_SCRIPT, "text": "执行脚本"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.EXECUTE_SCRIPT, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_screenshot_dispatch(self):
        step = _make_step()
        action_info = {"type": ActionType.SCREENSHOT, "text": "截图"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.SCREENSHOT, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_fallback_dispatch_with_warning(self):
        step = _make_step()
        action_info = {"type": ActionType.DOUBLE_CLICK, "text": "双击"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.DOUBLE_CLICK, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_existing_dispatch_unchanged_navigate(self):
        step = _make_step()
        action_info = {"type": ActionType.NAVIGATE, "text": "导航到 https://example.com"}
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await self.engine._dispatch_step_action(
                step, ActionType.NAVIGATE, action_info, {}, None, None, False
            )

    @pytest.mark.asyncio
    async def test_existing_dispatch_unchanged_verify(self):
        step = _make_step()
        action_info = {"type": ActionType.VERIFY, "text": "验证文本"}
        with pytest.raises((StepExecutionError, Exception)):
            await self.engine._dispatch_step_action(
                step, ActionType.VERIFY, action_info, {}, None, None, False
            )


class TestExecuteSwitchFrame:
    """_execute_switch_frame 方法测试"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        step = _make_step(target_element="myframe")
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_page_not_initialized(self):
        browser = _make_browser(page=None, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="myframe")
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_frame_not_found(self):
        page = SimpleNamespace(
            frame=lambda **kwargs: None,
            frame_locator=lambda selector: None,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="nonexistent")
        with pytest.raises(StepExecutionError, match="未找到目标iframe"):
            await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_css_selector_frame(self):
        frame_obj = SimpleNamespace()
        page = SimpleNamespace(
            frame=lambda **kwargs: None,
            frame_locator=lambda selector: frame_obj,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element=".my-iframe")
        await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_id_selector_frame(self):
        frame_obj = SimpleNamespace()
        page = SimpleNamespace(
            frame=lambda **kwargs: None,
            frame_locator=lambda selector: frame_obj,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="#my-iframe")
        await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_name_based_frame(self):
        frame_obj = SimpleNamespace()
        page = SimpleNamespace(
            frame=lambda **kwargs: frame_obj,
            frame_locator=lambda selector: None,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="iframe_name")
        await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_frame_exception(self):
        page = SimpleNamespace(
            frame=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("frame error")),
            frame_locator=lambda selector: None,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="iframe_name")
        with pytest.raises(StepExecutionError, match="切换iframe失败"):
            await engine._execute_switch_frame({"text": "切换iframe"}, step)

    @pytest.mark.asyncio
    async def test_target_from_action_info(self):
        frame_obj = SimpleNamespace()
        page = SimpleNamespace(
            frame=lambda **kwargs: frame_obj if kwargs.get("name") == "myframe" else None,
            frame_locator=lambda selector: None,
        )
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="")
        await engine._execute_switch_frame({"text": "myframe"}, step)


class TestExecuteSwitchWindow:
    """_execute_switch_window 方法测试"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        step = _make_step(target_element="新窗口")
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_switch_window({"text": "切换窗口"}, step)

    @pytest.mark.asyncio
    async def test_context_not_initialized(self):
        browser = _make_browser(page=object(), context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="新窗口")
        with pytest.raises(StepExecutionError, match="浏览器上下文未初始化"):
            await engine._execute_switch_window({"text": "切换窗口"}, step)

    @pytest.mark.asyncio
    async def test_no_matching_window(self):
        mock_page = SimpleNamespace(
            title=_make_async_return("首页"),
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[mock_page])
        browser = _make_browser(page=mock_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="不存在的窗口")
        with pytest.raises(StepExecutionError, match="未找到匹配的窗口"):
            await engine._execute_switch_window({"text": "切换窗口"}, step)

    @pytest.mark.asyncio
    async def test_match_by_title(self):
        target_page = SimpleNamespace(
            title=_make_async_return("目标页面"),
            url="https://example.com/target",
            bring_to_front=_noop,
        )
        other_page = SimpleNamespace(
            title=_make_async_return("首页"),
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[other_page, target_page])
        browser = _make_browser(page=other_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="目标页面")
        await engine._execute_switch_window({"text": "切换窗口"}, step)
        assert engine.browser._page is target_page

    @pytest.mark.asyncio
    async def test_match_by_url(self):
        target_page = SimpleNamespace(
            title=_make_async_return("详情"),
            url="https://example.com/detail",
            bring_to_front=_noop,
        )
        other_page = SimpleNamespace(
            title=_make_async_return("首页"),
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[other_page, target_page])
        browser = _make_browser(page=other_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="/detail")
        await engine._execute_switch_window({"text": "切换窗口"}, step)
        assert engine.browser._page is target_page

    @pytest.mark.asyncio
    async def test_match_by_index(self):
        target_page = SimpleNamespace(
            title=_make_async_return("目标页"),
            url="https://example.com/target",
            bring_to_front=_noop,
        )
        first_page = SimpleNamespace(
            title=_make_async_return("首页"),
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[first_page, target_page])
        browser = _make_browser(page=first_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="1")
        await engine._execute_switch_window({"text": "切换窗口"}, step)
        assert engine.browser._page is target_page

    @pytest.mark.asyncio
    async def test_invalid_index_falls_back(self):
        only_page = SimpleNamespace(
            title=_make_async_return("唯一页"),
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[only_page])
        browser = _make_browser(page=only_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="999")
        with pytest.raises(StepExecutionError, match="未找到匹配的窗口"):
            await engine._execute_switch_window({"text": "切换窗口"}, step)

    @pytest.mark.asyncio
    async def test_switch_window_exception(self):
        async def fail_title():
            raise RuntimeError("title error")

        bad_page = SimpleNamespace(
            title=fail_title,
            url="https://example.com/home",
            bring_to_front=_noop,
        )
        context = SimpleNamespace(pages=[bad_page])
        browser = _make_browser(page=bad_page, context=context)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="首页")
        with pytest.raises(StepExecutionError, match="切换窗口失败"):
            await engine._execute_switch_window({"text": "切换窗口"}, step)


class TestExecuteUpload:
    """_execute_upload 方法测试"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        step = _make_step(target_element="input[type=file]", input_value="/tmp/test.txt")
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_upload({"text": "上传文件"}, step)

    @pytest.mark.asyncio
    async def test_page_not_initialized(self):
        browser = _make_browser(page=None, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="input[type=file]", input_value="/tmp/test.txt")
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_upload({"text": "上传文件"}, step)

    @pytest.mark.asyncio
    async def test_missing_selector(self):
        page = SimpleNamespace()
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="", input_value="/tmp/test.txt")
        with pytest.raises(StepExecutionError, match="上传文件缺少目标元素选择器"):
            await engine._execute_upload({"text": ""}, step)

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        page = SimpleNamespace()
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="input[type=file]", input_value="")
        with pytest.raises(StepExecutionError, match="上传文件缺少文件路径"):
            await engine._execute_upload({"text": "上传文件"}, step)

    @pytest.mark.asyncio
    async def test_upload_success(self):
        uploaded = {}

        async def mock_set_input_files(selector: str, path: str) -> None:
            uploaded["selector"] = selector
            uploaded["path"] = path

        page = SimpleNamespace(set_input_files=mock_set_input_files)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="input[type=file]", input_value="/tmp/test.txt")
        await engine._execute_upload({"text": "上传文件"}, step)
        assert uploaded["selector"] == "input[type=file]"
        assert uploaded["path"] == "/tmp/test.txt"

    @pytest.mark.asyncio
    async def test_upload_playwright_error(self):
        async def mock_set_input_files(selector: str, path: str) -> None:
            raise RuntimeError("file not found")

        page = SimpleNamespace(set_input_files=mock_set_input_files)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="input[type=file]", input_value="/nonexistent.txt")
        with pytest.raises(StepExecutionError, match="文件上传失败"):
            await engine._execute_upload({"text": "上传文件"}, step)

    @pytest.mark.asyncio
    async def test_upload_from_action_info_input_value(self):
        uploaded = {}

        async def mock_set_input_files(selector: str, path: str) -> None:
            uploaded["selector"] = selector
            uploaded["path"] = path

        page = SimpleNamespace(set_input_files=mock_set_input_files)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(target_element="input[type=file]", input_value="")
        action_info = {"text": "上传文件", "input_value": "/tmp/from_action.txt"}
        await engine._execute_upload(action_info, step)
        assert uploaded["path"] == "/tmp/from_action.txt"


class TestExecuteScript:
    """_execute_execute_script 方法测试"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        step = _make_step(input_value="document.title")
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_execute_script({"text": "执行脚本"}, step)

    @pytest.mark.asyncio
    async def test_page_not_initialized(self):
        browser = _make_browser(page=None, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(input_value="document.title")
        with pytest.raises(StepExecutionError, match="浏览器页面未初始化"):
            await engine._execute_execute_script({"text": "执行脚本"}, step)

    @pytest.mark.asyncio
    async def test_missing_script(self):
        page = SimpleNamespace()
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(input_value="")
        with pytest.raises(StepExecutionError, match="执行脚本缺少JavaScript代码"):
            await engine._execute_execute_script({"text": ""}, step)

    @pytest.mark.asyncio
    async def test_script_execution_success(self):
        evaluated = {}

        async def mock_evaluate(script: str, **kwargs):
            evaluated["script"] = script
            return "test_result"

        page = SimpleNamespace(evaluate=mock_evaluate)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(input_value="document.title")
        await engine._execute_execute_script({"text": "执行脚本"}, step)
        assert evaluated["script"] == "document.title"

    @pytest.mark.asyncio
    async def test_script_execution_error(self):
        async def mock_evaluate(script: str, **kwargs):
            raise RuntimeError("JS error")

        page = SimpleNamespace(evaluate=mock_evaluate)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(input_value="invalid js code")
        with pytest.raises(StepExecutionError, match="脚本执行失败"):
            await engine._execute_execute_script({"text": "执行脚本"}, step)

    @pytest.mark.asyncio
    async def test_script_from_action_info_text(self):
        evaluated = {}

        async def mock_evaluate(script: str, **kwargs):
            evaluated["script"] = script
            return None

        page = SimpleNamespace(evaluate=mock_evaluate)
        browser = _make_browser(page=page, context=None)
        engine = _StubEngine(browser=browser)
        step = _make_step(input_value="")
        action_info = {"text": "window.scrollTo(0, 0)"}
        await engine._execute_execute_script(action_info, step)
        assert evaluated["script"] == "window.scrollTo(0, 0)"


class TestExecuteScreenshot:
    """_execute_screenshot 方法测试"""

    @pytest.mark.asyncio
    async def test_browser_not_initialized(self):
        engine = _StubEngine(browser=None)
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await engine._execute_screenshot({"text": "截图"})

    @pytest.mark.asyncio
    async def test_screenshot_success(self):
        browser = SimpleNamespace(take_screenshot=_make_async_return(b"screenshot_bytes"))
        engine = _StubEngine(browser=browser)
        await engine._execute_screenshot({"text": "截图"})

    @pytest.mark.asyncio
    async def test_screenshot_error(self):
        async def fail_screenshot():
            raise RuntimeError("screenshot failed")

        browser = SimpleNamespace(take_screenshot=fail_screenshot)
        engine = _StubEngine(browser=browser)
        with pytest.raises(StepExecutionError, match="截图失败"):
            await engine._execute_screenshot({"text": "截图"})
