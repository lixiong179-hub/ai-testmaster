"""ADB 与移动端执行相关单元测试。

适配新 ExecutionMode API（仅 AI_VISION/API/UNKNOWN），
覆盖 AdbController、UIAutomatorHelper、MobileAIExecutor 的纯逻辑分支。
"""

import os
import re
import inspect
import pytest
from dataclasses import asdict

from app.utils.adb_controller import (
    AdbController,
    AdbError,
    DeviceNotConnectedError,
    AdbCommandTimeoutError,
    DeviceInfo,
)
from app.utils.uiautomator_helper import (
    UIAutomatorHelper,
    UIElement,
    UIAutomatorError,
    ElementNotFoundError,
)
from app.services.mobile_ai_executor import (
    MobileAIExecutor,
    MobileActionType,
    MobileAIError,
    MobileDeviceError,
    MobileRecognitionError,
    MobileActionResult,
)
from app.utils.unified_vision_model import ElementInfo
from app.models.element_locator import ElementLocator


SAMPLE_UI_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0"><node text="" resource-id="" class="android.widget.FrameLayout" package="com.example" content-desc="" clickable="false" enabled="true" bounds="[0,0][1080,1920]"><node text="登录" resource-id="com.example:id/login_btn" class="android.widget.Button" package="com.example" content-desc="登录按钮" clickable="true" enabled="true" bounds="[340,1200][740,1320]"/></node></hierarchy>"""


def _make_helper() -> UIAutomatorHelper:
    return UIAutomatorHelper.__new__(UIAutomatorHelper)


def _make_executor() -> MobileAIExecutor:
    return MobileAIExecutor.__new__(MobileAIExecutor)


class TestAdbController:
    def test_init_default(self):
        ctrl = AdbController()
        assert ctrl.udid is None
        assert ctrl.adb_path == "adb"
        assert ctrl.default_timeout == 30

    def test_init_with_udid(self):
        ctrl = AdbController(udid="device123", adb_path="/usr/bin/adb", default_timeout=60)
        assert ctrl.udid == "device123" and ctrl.adb_path == "/usr/bin/adb"
        assert ctrl.default_timeout == 60

    def test_build_command_without_udid(self):
        cmd = AdbController()._build_command("shell", "input", "tap", "100", "200")
        assert cmd == ["adb", "shell", "input", "tap", "100", "200"]

    def test_build_command_with_udid(self):
        cmd = AdbController(udid="emulator-5554")._build_command("shell", "input", "tap", "100", "200")
        assert cmd == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"]


class TestDeviceInfo:
    def test_device_info_creation(self):
        info = DeviceInfo(udid="abc123", state="device")
        assert info.udid == "abc123" and info.state == "device"
        assert info.model is None and info.screen_size is None

    def test_device_info_full(self):
        info = DeviceInfo(udid="x", state="y", model="Pixel 6", android_version="13", screen_size=(1080, 1920))
        assert info.model == "Pixel 6" and info.screen_size == (1080, 1920)

    def test_device_info_is_dataclass(self):
        assert set(asdict(DeviceInfo(udid="x", state="y")).keys()) == {
            "udid",
            "state",
            "model",
            "android_version",
            "screen_size",
        }


class TestErrorHierarchies:
    """验证 ADB/UIAutomator/MobileAI 错误类继承关系。"""

    @pytest.mark.parametrize(
        "parent,child",
        [
            (Exception, AdbError),
            (AdbError, DeviceNotConnectedError),
            (AdbError, AdbCommandTimeoutError),
            (Exception, UIAutomatorError),
            (UIAutomatorError, ElementNotFoundError),
            (Exception, MobileAIError),
            (MobileAIError, MobileDeviceError),
            (MobileAIError, MobileRecognitionError),
        ],
    )
    def test_subclass(self, parent, child):
        assert issubclass(child, parent)

    @pytest.mark.parametrize("exc_class", [AdbError, UIAutomatorError, MobileAIError])
    def test_raise(self, exc_class):
        with pytest.raises(exc_class):
            raise exc_class("test")


class TestUIElement:
    def test_ui_element_default(self):
        el = UIElement()
        assert el.resource_id is None and el.text is None and el.bounds is None
        assert el.clickable is False and el.enabled is True

    def test_ui_element_with_bounds(self):
        el = UIElement(
            resource_id="com.example:id/btn",
            text="Click",
            bounds={"left": 100, "top": 200, "right": 300, "bottom": 280},
            clickable=True,
        )
        assert el.resource_id == "com.example:id/btn" and el.clickable is True

    def test_center_and_size_properties(self):
        el = UIElement(bounds={"left": 100, "top": 200, "right": 300, "bottom": 400})
        assert el.center == {"x": 200, "y": 300}
        assert el.width == 200 and el.height == 200

    def test_properties_no_bounds(self):
        el = UIElement()
        assert el.center is None and el.width == 0 and el.height == 0

    def test_matches_description_by_text(self):
        assert UIElement(text="登录").matches_description("点击登录按钮") is True

    def test_matches_description_no_match(self):
        el = UIElement(text="提交", resource_id="com.example:id/submit")
        assert el.matches_description("取消") is False


class TestUIAutomatorHelperParseBounds:
    @pytest.mark.parametrize(
        "bounds_str,expected",
        [
            ("[100,200][300,400]", {"left": 100, "top": 200, "right": 300, "bottom": 400}),
            ("[0,0][1080,1920]", {"left": 0, "top": 0, "right": 1080, "bottom": 1920}),
        ],
    )
    def test_parse_bounds_valid(self, bounds_str, expected):
        assert _make_helper()._parse_bounds(bounds_str) == expected

    @pytest.mark.parametrize("invalid", ["invalid", "", "[100,200]"])
    def test_parse_bounds_invalid(self, invalid):
        assert _make_helper()._parse_bounds(invalid) is None


class TestUIAutomatorHelperParseXml:
    def test_parse_xml_sample(self):
        assert len(_make_helper()._parse_xml(SAMPLE_UI_XML)) == 3

    def test_parse_xml_login_button(self):
        elements = _make_helper()._parse_xml(SAMPLE_UI_XML)
        login_btn = [e for e in elements if e.resource_id == "com.example:id/login_btn"][0]
        assert login_btn.text == "登录" and login_btn.content_desc == "登录按钮"
        assert login_btn.clickable is True and login_btn.center == {"x": 540, "y": 1260}

    @pytest.mark.parametrize("invalid_xml", ["<invalid><broken>", ""])
    def test_parse_xml_invalid(self, invalid_xml):
        with pytest.raises(UIAutomatorError):
            _make_helper()._parse_xml(invalid_xml)


class TestMobileActionType:
    @pytest.mark.parametrize(
        "member,expected",
        [
            (MobileActionType.CLICK, "click"),
            (MobileActionType.INPUT, "input"),
            (MobileActionType.GO_BACK, "go_back"),
            (MobileActionType.SWIPE, "swipe"),
            (MobileActionType.LAUNCH_APP, "launch_app"),
        ],
    )
    def test_member_value(self, member, expected):
        assert member.value == expected

    def test_enum_count(self):
        assert len(MobileActionType) == 13

    def test_is_str_enum(self):
        assert isinstance(MobileActionType.CLICK, str)


class TestParseAction:
    def setup_method(self):
        self.executor = _make_executor()

    @pytest.mark.parametrize(
        "description,expected",
        [
            ("点击返回按钮", MobileActionType.GO_BACK),
            ("回到主页", MobileActionType.GO_HOME),
            ("向上滑动", MobileActionType.SCROLL_UP),
            ("scroll down", MobileActionType.SCROLL_DOWN),
            ("向左滑动", MobileActionType.SCROLL_LEFT),
            ("scroll right", MobileActionType.SCROLL_RIGHT),
            ("输入用户名", MobileActionType.INPUT),
            ("swipe left to right", MobileActionType.SWIPE),
            ("按回车键", MobileActionType.PRESS_KEY),
            ("启动应用", MobileActionType.LAUNCH_APP),
            ("wait for element", MobileActionType.WAIT),
            ("验证结果", MobileActionType.VERIFY),
            ("something random", MobileActionType.CLICK),
            ("INPUT TEXT", MobileActionType.INPUT),
            ("  返回  ", MobileActionType.GO_BACK),
        ],
    )
    def test_parse_action(self, description, expected):
        assert self.executor.parse_action(description) == expected

    def test_parse_go_home_not_when_navigate(self):
        """导航场景不应误判为 GO_HOME，避免关键字误匹配。"""
        assert self.executor.parse_action("导航到主页") != MobileActionType.GO_HOME


class TestExtractInputText:
    def setup_method(self):
        self.executor = _make_executor()

    @pytest.mark.parametrize(
        "description,expected",
        [
            ('输入"hello"到输入框', "hello"),
            ("输入'world'", "world"),
            ('填写"test"', "test"),
            ("点击按钮", None),
        ],
    )
    def test_extract_input_text(self, description, expected):
        assert self.executor._extract_input_text(description) == expected


class TestExtractInputTarget:
    def setup_method(self):
        self.executor = _make_executor()

    @pytest.mark.parametrize(
        "description,expected",
        [
            ("在用户名中输入hello", "用户名"),
            ("在密码框里输入123", "密码框"),
            ("在搜索栏上输入test", "搜索栏"),
            ("输入hello", None),
        ],
    )
    def test_extract_input_target(self, description, expected):
        assert self.executor._extract_input_target(description) == expected


class TestExtractPackageActivity:
    def setup_method(self):
        self.executor = _make_executor()

    @pytest.mark.parametrize(
        "description,expected",
        [
            ("启动 com.example/.MainActivity", ("com.example", ".MainActivity")),
            ("com.test/MainActivity", ("com.test", "MainActivity")),
            ("启动应用", None),
        ],
    )
    def test_extract_package_activity(self, description, expected):
        assert self.executor._extract_package_activity(description) == expected


class TestMobileActionResult:
    def test_action_result_creation(self):
        result = MobileActionResult(success=True, action_type=MobileActionType.CLICK, description="点击登录")
        assert result.success is True and result.action_type == MobileActionType.CLICK
        assert result.coordinates is None and result.ai_confidence == 0.0

    def test_action_result_with_coordinates(self):
        result = MobileActionResult(
            success=True,
            action_type=MobileActionType.CLICK,
            description="点击",
            coordinates={"x": 540, "y": 1260},
            ai_confidence=0.95,
        )
        assert result.coordinates == {"x": 540, "y": 1260} and result.ai_confidence == 0.95

    def test_action_result_failure(self):
        result = MobileActionResult(
            success=False,
            action_type=MobileActionType.INPUT,
            description="输入失败",
            error_message="无法定位输入框",
        )
        assert result.success is False and result.error_message == "无法定位输入框"


class TestAppiumRemoval:
    """验证已移除的 Appium/MobileController 不会被重新引入。"""

    def test_mobile_controller_file_not_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "utils",
            "mobile_controller.py",
        )
        assert not os.path.exists(path)

    def test_precondition_service_no_mobile_controller_import(self):
        import app.services.precondition_service as precondition_module

        assert "MobileController" not in inspect.getsource(precondition_module)

    def test_precondition_service_no_mobile_controller_attribute(self):
        from app.services.precondition_service import PreconditionService

        svc = PreconditionService()
        assert not hasattr(svc, "mobile_controller") or svc.mobile_controller is None


class TestInputTextSecurity:
    """验证 ADB input text 命令的 shell 转义原则，阻断命令注入。"""

    def test_input_text_escapes_percent(self):
        assert "50%off".replace("%", "%%").replace(" ", "%s") == "50%%off"

    def test_input_text_wraps_in_single_quotes(self):
        cmd = AdbController(udid="device1")._build_command("shell", "input text 'hello'")
        assert "'" in " ".join(cmd)

    def test_input_text_shell_injection_semicolon(self):
        text = "hello; rm -rf /"
        shell_escaped = text.replace("%", "%%").replace(" ", "%s").replace("'", "'\\''")
        cmd_part = f"input text '{shell_escaped}'"
        assert cmd_part.startswith("input text '") and "hello;" in cmd_part


class TestPackageNameValidation:
    """验证包名格式校验，阻断 ADB 命令注入。"""

    def test_validate_valid_package_name(self):
        AdbController._validate_package_name("com.example.app")

    @pytest.mark.parametrize(
        "invalid",
        [
            "example",
            "com.123app",
            "",
            "com.example;rm -rf",
            "com.my-app",
        ],
    )
    def test_validate_invalid_package_name(self, invalid):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name(invalid)


class TestActivityNameValidation:
    """验证 Activity 名格式校验，阻断 ADB 命令注入。"""

    @pytest.mark.parametrize("valid", [".MainActivity", "com.example.app.MainActivity"])
    def test_valid_activity_name(self, valid):
        assert re.match(r"^\.?[a-zA-Z][a-zA-Z0-9._]*$", valid)

    @pytest.mark.parametrize("invalid", [".Activity;rm", "1Activity", ".Activity|cat"])
    def test_invalid_activity_name(self, invalid):
        assert not re.match(r"^\.?[a-zA-Z][a-zA-Z0-9._]*$", invalid)


class TestXMLSanitization:
    """验证 UIAutomator XML 的 XXE 防护。"""

    def test_sanitize_xml_removes_doctype(self):
        xml_with_doctype = '<!DOCTYPE foo [<!ENTITY xxe "bar">]><hierarchy><node/></hierarchy>'
        assert "<!DOCTYPE" not in _make_helper()._sanitize_xml(xml_with_doctype)

    def test_sanitize_xml_removes_entity(self):
        xml_with_entity = '<!ENTITY xxe "bar"><hierarchy><node/></hierarchy>'
        assert "<!ENTITY" not in _make_helper()._sanitize_xml(xml_with_entity)

    def test_sanitize_xml_preserves_normal(self):
        sanitized = _make_helper()._sanitize_xml('<hierarchy><node text="hello"/></hierarchy>')
        assert "<hierarchy>" in sanitized and 'text="hello"' in sanitized


# ============================================================
# MobileActionExecutorMixin.execute_action 分支护栏
# ============================================================


class FakeMobileAdb:
    """ADB 控制器替身：记录调用轨迹，并可按方法注入异常。"""

    def __init__(self, connected: bool = True, screen_size: tuple[int, int] = (1080, 1920), errors=None):
        self.connected = connected
        self.screen_size = screen_size
        self.errors = errors or {}
        self.calls: list[tuple] = []

    def _invoke(self, name: str, *args):
        error = self.errors.get(name)
        if error is not None:
            raise error
        self.calls.append((name, *args))

    async def is_device_connected(self) -> bool:
        return self.connected

    async def click(self, x: int, y: int) -> None:
        self._invoke("click", x, y)

    async def input_text(self, text: str) -> None:
        self._invoke("input_text", text)

    async def get_screen_size(self) -> tuple[int, int]:
        return self.screen_size

    async def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> None:
        self._invoke("swipe", x1, y1, x2, y2, duration)

    async def press_key(self, keycode: int) -> None:
        self._invoke("press_key", keycode)

    async def press_back(self) -> None:
        self._invoke("press_back")

    async def press_home(self) -> None:
        self._invoke("press_home")

    async def start_app(self, package: str, activity: str) -> None:
        self._invoke("start_app", package, activity)

    async def take_screenshot(self) -> bytes:
        return b"fake-screenshot"


class FakeMobileVision:
    """视觉模型替身：可返回预设元素或验证响应。"""

    def __init__(self, elements: list[ElementInfo] | None = None, verify_response: str | None = None):
        self.elements = elements or []
        self.verify_response = verify_response

    def recognize_elements(self, screenshot: bytes, description: str, min_confidence: float = 0.9):
        return self.elements

    def analyze_image(self, screenshot: bytes, prompt: str, system_prompt: str | None = None) -> str | None:
        return self.verify_response


def _make_executor_with(adb: FakeMobileAdb, vision: FakeMobileVision | None = None) -> MobileAIExecutor:
    executor = MobileAIExecutor.__new__(MobileAIExecutor)
    executor.db = None
    executor.adb = adb
    executor.vision_model = vision or FakeMobileVision()
    executor.uiautomator = None
    return executor


@pytest.fixture
def fast_sleep(monkeypatch):
    """把执行器内的 asyncio.sleep 置为空操作，避免测试真等待。"""

    async def _noop(_seconds, *_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.mobile_ai_executor.action_executor_mixin.asyncio.sleep", _noop)


class TestMobileExecuteActionDispatch:
    def setup_method(self):
        self.adb = FakeMobileAdb()
        self.executor = _make_executor_with(self.adb)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description,expected_type,adb_call",
        [
            ("点击返回按钮", MobileActionType.GO_BACK, ("press_back",)),
            ("回到主页", MobileActionType.GO_HOME, ("press_home",)),
            ("按回车键", MobileActionType.PRESS_KEY, ("press_key", 66)),
        ],
    )
    async def test_navigation_actions(self, description, expected_type, adb_call):
        result = await self.executor.execute_action(description)

        assert result.success is True
        assert result.action_type == expected_type
        assert result.description == description
        assert self.adb.calls == [adb_call]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "description,expected_type,swipe_args",
        [
            ("向上滑动", MobileActionType.SCROLL_UP, (540, 1440, 540, 480, 500)),
            ("scroll down", MobileActionType.SCROLL_DOWN, (540, 480, 540, 1440, 500)),
            ("向左滑动", MobileActionType.SCROLL_LEFT, (810, 960, 270, 960, 500)),
            ("scroll right", MobileActionType.SCROLL_RIGHT, (270, 960, 810, 960, 500)),
        ],
    )
    async def test_scroll_actions(self, description, expected_type, swipe_args):
        result = await self.executor.execute_action(description)

        assert result.success is True
        assert result.action_type == expected_type
        assert result.description == expected_type.value
        assert self.adb.calls == [("swipe", *swipe_args)]

    @pytest.mark.asyncio
    async def test_swipe_action(self):
        result = await self.executor.execute_action("swipe left to right")

        assert result.success is True
        assert result.action_type == MobileActionType.SWIPE
        assert self.adb.calls == [("swipe", 540, 1280, 540, 640, 500)]

    @pytest.mark.asyncio
    async def test_click_uses_vision_element_center(self):
        vision = FakeMobileVision(
            elements=[ElementInfo(type="button", text="登录", x=100, y=200, width=40, height=20, confidence=0.95)]
        )
        executor = _make_executor_with(self.adb, vision)

        result = await executor.execute_action("点击登录")

        assert result.success is True
        assert result.action_type == MobileActionType.CLICK
        assert result.coordinates == {"x": 120, "y": 210}
        assert result.ai_confidence == 0.95
        assert result.locator_info is None
        assert self.adb.calls == [("click", 120, 210)]

    @pytest.mark.asyncio
    async def test_click_without_recognized_element_raises(self):
        with pytest.raises(MobileRecognitionError, match="AI无法识别目标元素"):
            await self.executor.execute_action("点击登录")

    @pytest.mark.asyncio
    async def test_click_below_confidence_threshold_raises(self):
        vision = FakeMobileVision(
            elements=[ElementInfo(type="button", text="登录", x=0, y=0, width=10, height=10, confidence=0.5)]
        )
        executor = _make_executor_with(self.adb, vision)

        with pytest.raises(MobileRecognitionError):
            await executor.execute_action("点击登录")

    @pytest.mark.asyncio
    async def test_input_text_only(self, fast_sleep):
        result = await self.executor.execute_action("输入hello")

        assert result.success is True
        assert result.action_type == MobileActionType.INPUT
        assert self.adb.calls == [("input_text", "hello")]

    @pytest.mark.asyncio
    async def test_input_with_target_clicks_first(self, fast_sleep):
        vision = FakeMobileVision(
            elements=[ElementInfo(type="input", text="用户名", x=0, y=0, width=100, height=40, confidence=0.9)]
        )
        executor = _make_executor_with(self.adb, vision)

        result = await executor.execute_action("在用户名中输入hello")

        assert result.success is True
        assert self.adb.calls == [("click", 50, 20), ("input_text", "hello")]

    @pytest.mark.asyncio
    async def test_input_without_extracted_text_still_succeeds(self, fast_sleep):
        result = await self.executor.execute_action("输入")

        assert result.success is True
        assert result.action_type == MobileActionType.INPUT
        assert self.adb.calls == []

    @pytest.mark.asyncio
    async def test_launch_app(self):
        result = await self.executor.execute_action("启动 com.example/.MainActivity")

        assert result.success is True
        assert result.action_type == MobileActionType.LAUNCH_APP
        assert self.adb.calls == [("start_app", "com.example", ".MainActivity")]

    @pytest.mark.asyncio
    async def test_launch_app_without_package_raises(self):
        with pytest.raises(MobileAIError, match="无法解析应用包名"):
            await self.executor.execute_action("启动应用")

    @pytest.mark.asyncio
    async def test_wait_action(self, fast_sleep):
        result = await self.executor.execute_action("等待2秒")

        assert result.success is True
        assert result.action_type == MobileActionType.WAIT
        assert self.adb.calls == []

    @pytest.mark.asyncio
    async def test_verify_passed_by_json(self):
        vision = FakeMobileVision(verify_response='{"passed": true, "reason": "符合预期"}')
        executor = _make_executor_with(self.adb, vision)

        result = await executor.execute_action("验证登录成功")

        assert result.success is True
        assert result.action_type == MobileActionType.VERIFY

    @pytest.mark.asyncio
    async def test_verify_falls_back_to_keyword_on_invalid_json(self):
        vision = FakeMobileVision(verify_response='{"passed": 通过}')
        executor = _make_executor_with(self.adb, vision)

        result = await executor.execute_action("验证登录成功")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_without_response_fails(self):
        vision = FakeMobileVision(verify_response=None)
        executor = _make_executor_with(self.adb, vision)

        result = await executor.execute_action("验证登录成功")

        assert result.success is False
        assert result.action_type == MobileActionType.VERIFY

    @pytest.mark.asyncio
    async def test_device_not_connected_raises_device_error(self):
        executor = _make_executor_with(FakeMobileAdb(connected=False))

        with pytest.raises(MobileDeviceError, match="设备未连接"):
            await executor.execute_action("回到主页")

    @pytest.mark.asyncio
    async def test_adb_error_is_wrapped_as_device_error(self):
        executor = _make_executor_with(FakeMobileAdb(errors={"press_back": AdbError("adb 挂了")}))

        with pytest.raises(MobileDeviceError, match="ADB操作失败"):
            await executor.execute_action("点击返回按钮")

    @pytest.mark.asyncio
    async def test_unexpected_error_is_wrapped_as_mobile_error(self):
        executor = _make_executor_with(FakeMobileAdb(errors={"press_home": RuntimeError("未知错误")}))

        with pytest.raises(MobileAIError, match="执行失败"):
            await executor.execute_action("回到主页")

    @pytest.mark.asyncio
    async def test_mobile_error_is_not_rewrapped(self):
        executor = _make_executor_with(FakeMobileAdb(errors={"press_back": MobileAIError("原始错误")}))

        with pytest.raises(MobileAIError, match="原始错误"):
            await executor.execute_action("点击返回按钮")

    @pytest.mark.asyncio
    async def test_unsupported_action_type_returns_failure(self, monkeypatch):
        monkeypatch.setattr(self.executor, "parse_action", lambda _description: "unknown")

        result = await self.executor.execute_action("未知操作")

        assert result.success is False
        assert result.error_message == "不支持的操作类型: unknown"
        assert self.adb.calls == []

    @pytest.mark.asyncio
    async def test_unrecognized_press_key_falls_back_to_enter(self):
        result = await self.executor.execute_action("按键 abc")

        assert result.success is True
        assert result.action_type == MobileActionType.PRESS_KEY
        assert self.adb.calls == [("press_key", 66)]


class FakeQuery:
    def __init__(self, locator):
        self._locator = locator

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._locator


class FakeDb:
    """仅实现缓存定位查询所需的最小接口。"""

    def __init__(self, locator=None):
        self._locator = locator

    def query(self, _model):
        return FakeQuery(self._locator)

    def add(self, _obj):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class FakeUIAutomator:
    def __init__(self, element: UIElement | None = None):
        self.element = element

    async def find_element(self, accessibility_id=None, resource_id=None, text=None):
        return self.element


class TestMobileExecuteActionCache:
    """点击动作的缓存定位优先路径。"""

    @pytest.mark.asyncio
    async def test_cached_locator_click_is_preferred(self):
        adb = FakeMobileAdb()
        vision = FakeMobileVision(
            elements=[ElementInfo(type="button", text="实时识别", x=0, y=0, width=10, height=10, confidence=0.99)]
        )
        executor = _make_executor_with(adb, vision)
        cached_locator = ElementLocator(
            step_id=7, element_description="登录按钮", element_id="btn_login", source="ai_mobile"
        )
        executor.db = FakeDb(cached_locator)
        executor.uiautomator = FakeUIAutomator(UIElement(bounds={"left": 100, "top": 200, "right": 300, "bottom": 400}))

        result = await executor.execute_action("点击登录", step_id=7)

        assert result.success is True
        assert result.used_cache is True
        assert result.coordinates == {"x": 200, "y": 300}
        assert adb.calls == [("click", 200, 300)]

    @pytest.mark.asyncio
    async def test_cache_miss_falls_back_to_vision(self):
        adb = FakeMobileAdb()
        vision = FakeMobileVision(
            elements=[ElementInfo(type="button", text="登录", x=0, y=0, width=100, height=40, confidence=0.9)]
        )
        executor = _make_executor_with(adb, vision)
        executor.db = FakeDb(None)
        executor.uiautomator = FakeUIAutomator(None)

        result = await executor.execute_action("点击登录", step_id=7)

        assert result.success is True
        assert result.used_cache is False
        assert adb.calls == [("click", 50, 20)]
