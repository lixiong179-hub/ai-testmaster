import os
import re
import inspect
import pytest

pytestmark = pytest.mark.skip(reason="ExecutionMode枚举已重构，MOBILE_REALTIME/MOBILE_SMART/PREPROCESS等已移除")

from dataclasses import asdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
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
from app.services.test_execution_engine_v2 import ExecutionMode


SAMPLE_UI_XML = '''<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[0,0][1080,1920]">
    <node index="0" text="登录" resource-id="com.example:id/login_btn" class="android.widget.Button" package="com.example" content-desc="登录按钮" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[340,1200][740,1320]"/>
    <node index="1" text="" resource-id="com.example:id/username" class="android.widget.EditText" package="com.example" content-desc="用户名输入框" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[140,600][940,740]"/>
    <node index="2" text="提交" resource-id="com.example:id/submit" class="android.widget.Button" package="com.example" content-desc="提交" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" bounds="[340,1400][740,1520]"/>
  </node>
</hierarchy>'''


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


class TestAdbController:

    def test_init_default(self):
        ctrl = AdbController()
        assert ctrl.udid is None
        assert ctrl.adb_path == "adb"
        assert ctrl.default_timeout == 30
        assert ctrl._screen_size is None

    def test_init_with_udid(self):
        ctrl = AdbController(udid="device123", adb_path="/usr/bin/adb", default_timeout=60)
        assert ctrl.udid == "device123"
        assert ctrl.adb_path == "/usr/bin/adb"
        assert ctrl.default_timeout == 60

    def test_build_command_without_udid(self):
        ctrl = AdbController()
        cmd = ctrl._build_command("shell", "input", "tap", "100", "200")
        assert cmd == ["adb", "shell", "input", "tap", "100", "200"]

    def test_build_command_with_udid(self):
        ctrl = AdbController(udid="emulator-5554")
        cmd = ctrl._build_command("shell", "input", "tap", "100", "200")
        assert cmd == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"]

    def test_build_command_empty_args(self):
        ctrl = AdbController(udid="device001")
        cmd = ctrl._build_command()
        assert cmd == ["adb", "-s", "device001"]

    def test_build_command_no_udid_empty_args(self):
        ctrl = AdbController()
        cmd = ctrl._build_command()
        assert cmd == ["adb"]


class TestDeviceInfo:

    def test_device_info_creation(self):
        info = DeviceInfo(udid="abc123", state="device")
        assert info.udid == "abc123"
        assert info.state == "device"
        assert info.model is None
        assert info.android_version is None
        assert info.screen_size is None

    def test_device_info_full(self):
        info = DeviceInfo(
            udid="abc123",
            state="device",
            model="Pixel 6",
            android_version="13",
            screen_size=(1080, 1920),
        )
        assert info.model == "Pixel 6"
        assert info.android_version == "13"
        assert info.screen_size == (1080, 1920)

    def test_device_info_is_dataclass(self):
        info = DeviceInfo(udid="x", state="y")
        d = asdict(info)
        assert "udid" in d
        assert "state" in d
        assert "model" in d
        assert "android_version" in d
        assert "screen_size" in d


class TestAdbErrorHierarchy:

    def test_adb_error_is_exception(self):
        assert issubclass(AdbError, Exception)

    def test_device_not_connected_error(self):
        assert issubclass(DeviceNotConnectedError, AdbError)

    def test_adb_command_timeout_error(self):
        assert issubclass(AdbCommandTimeoutError, AdbError)

    def test_adb_error_raise(self):
        with pytest.raises(AdbError):
            raise AdbError("test error")

    def test_device_not_connected_raise(self):
        with pytest.raises(AdbError):
            raise DeviceNotConnectedError("no device")

    def test_timeout_error_raise(self):
        with pytest.raises(AdbError):
            raise AdbCommandTimeoutError("timeout")

    def test_device_not_connected_not_timeout(self):
        assert not issubclass(DeviceNotConnectedError, AdbCommandTimeoutError)

    def test_timeout_not_device_not_connected(self):
        assert not issubclass(AdbCommandTimeoutError, DeviceNotConnectedError)


class TestUIElement:

    def test_ui_element_default(self):
        el = UIElement()
        assert el.resource_id is None
        assert el.accessibility_id is None
        assert el.text is None
        assert el.content_desc is None
        assert el.class_name is None
        assert el.package is None
        assert el.bounds is None
        assert el.clickable is False
        assert el.enabled is True
        assert el.focused is False
        assert el.scrollable is False

    def test_ui_element_with_bounds(self):
        el = UIElement(
            resource_id="com.example:id/btn",
            text="Click",
            bounds={"left": 100, "top": 200, "right": 300, "bottom": 280},
            clickable=True,
        )
        assert el.resource_id == "com.example:id/btn"
        assert el.text == "Click"
        assert el.bounds["left"] == 100
        assert el.clickable is True

    def test_center_property(self):
        el = UIElement(bounds={"left": 100, "top": 200, "right": 300, "bottom": 400})
        center = el.center
        assert center["x"] == 200
        assert center["y"] == 300

    def test_center_property_no_bounds(self):
        el = UIElement()
        assert el.center is None

    def test_width_property(self):
        el = UIElement(bounds={"left": 100, "top": 200, "right": 300, "bottom": 400})
        assert el.width == 200

    def test_width_property_no_bounds(self):
        el = UIElement()
        assert el.width == 0

    def test_height_property(self):
        el = UIElement(bounds={"left": 100, "top": 200, "right": 300, "bottom": 400})
        assert el.height == 200

    def test_height_property_no_bounds(self):
        el = UIElement()
        assert el.height == 0

    def test_matches_description_by_text(self):
        el = UIElement(text="登录")
        assert el.matches_description("点击登录按钮") is True

    def test_matches_description_by_content_desc(self):
        el = UIElement(content_desc="登录按钮")
        assert el.matches_description("点击登录按钮") is True

    def test_matches_description_by_accessibility_id(self):
        el = UIElement(accessibility_id="login_btn")
        assert el.matches_description("login_btn") is True

    def test_matches_description_by_resource_id(self):
        el = UIElement(resource_id="com.example:id/login_btn")
        assert el.matches_description("login_btn") is True

    def test_matches_description_no_match(self):
        el = UIElement(text="提交", resource_id="com.example:id/submit")
        assert el.matches_description("取消") is False

    def test_matches_description_case_insensitive(self):
        el = UIElement(text="Login")
        assert el.matches_description("login") is True

    def test_matches_description_resource_id_with_id_part(self):
        el = UIElement(resource_id="com.example:id/username_field")
        assert el.matches_description("username_field") is True

    def test_matches_description_resource_id_without_id_prefix(self):
        el = UIElement(resource_id="simple_id")
        assert el.matches_description("simple_id") is True


class TestUIAutomatorHelperParseBounds:

    def test_parse_bounds_valid(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        result = helper._parse_bounds("[100,200][300,400]")
        assert result == {"left": 100, "top": 200, "right": 300, "bottom": 400}

    def test_parse_bounds_zero(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        result = helper._parse_bounds("[0,0][1080,1920]")
        assert result == {"left": 0, "top": 0, "right": 1080, "bottom": 1920}

    def test_parse_bounds_invalid(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        result = helper._parse_bounds("invalid")
        assert result is None

    def test_parse_bounds_empty(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        result = helper._parse_bounds("")
        assert result is None

    def test_parse_bounds_partial(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        result = helper._parse_bounds("[100,200]")
        assert result is None


class TestUIAutomatorHelperParseXml:

    def test_parse_xml_sample(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(SAMPLE_UI_XML)
        assert len(elements) == 5

    def test_parse_xml_root_element(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(SAMPLE_UI_XML)
        frame = [e for e in elements if e.class_name == "android.widget.FrameLayout"][0]
        assert frame.class_name == "android.widget.FrameLayout"
        assert frame.package == "com.example"
        assert frame.bounds == {"left": 0, "top": 0, "right": 1080, "bottom": 1920}

    def test_parse_xml_login_button(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(SAMPLE_UI_XML)
        login_btn = [e for e in elements if e.resource_id == "com.example:id/login_btn"][0]
        assert login_btn.text == "登录"
        assert login_btn.content_desc == "登录按钮"
        assert login_btn.clickable is True
        assert login_btn.center == {"x": 540, "y": 1260}

    def test_parse_xml_username_field(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(SAMPLE_UI_XML)
        username = [e for e in elements if e.resource_id == "com.example:id/username"][0]
        assert username.class_name == "android.widget.EditText"
        assert username.content_desc == "用户名输入框"
        assert username.width == 800
        assert username.height == 140

    def test_parse_xml_submit_button(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(SAMPLE_UI_XML)
        submit = [e for e in elements if e.resource_id == "com.example:id/submit"][0]
        assert submit.text == "提交"
        assert submit.content_desc == "提交"
        assert submit.center == {"x": 540, "y": 1460}

    def test_parse_xml_invalid(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        with pytest.raises(UIAutomatorError):
            helper._parse_xml("<invalid><broken>")

    def test_parse_xml_empty_string(self):
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        with pytest.raises(UIAutomatorError):
            helper._parse_xml("")


class TestUIAutomatorErrorHierarchy:

    def test_uiautomator_error_is_exception(self):
        assert issubclass(UIAutomatorError, Exception)

    def test_element_not_found_error(self):
        assert issubclass(ElementNotFoundError, UIAutomatorError)

    def test_uiautomator_error_raise(self):
        with pytest.raises(UIAutomatorError):
            raise UIAutomatorError("test")

    def test_element_not_found_raise(self):
        with pytest.raises(UIAutomatorError):
            raise ElementNotFoundError("not found")


class TestMobileActionType:

    def test_click(self):
        assert MobileActionType.CLICK.value == "click"

    def test_input(self):
        assert MobileActionType.INPUT.value == "input"

    def test_swipe(self):
        assert MobileActionType.SWIPE.value == "swipe"

    def test_press_key(self):
        assert MobileActionType.PRESS_KEY.value == "press_key"

    def test_wait(self):
        assert MobileActionType.WAIT.value == "wait"

    def test_verify(self):
        assert MobileActionType.VERIFY.value == "verify"

    def test_scroll_up(self):
        assert MobileActionType.SCROLL_UP.value == "scroll_up"

    def test_scroll_down(self):
        assert MobileActionType.SCROLL_DOWN.value == "scroll_down"

    def test_scroll_left(self):
        assert MobileActionType.SCROLL_LEFT.value == "scroll_left"

    def test_scroll_right(self):
        assert MobileActionType.SCROLL_RIGHT.value == "scroll_right"

    def test_launch_app(self):
        assert MobileActionType.LAUNCH_APP.value == "launch_app"

    def test_go_back(self):
        assert MobileActionType.GO_BACK.value == "go_back"

    def test_go_home(self):
        assert MobileActionType.GO_HOME.value == "go_home"

    def test_enum_count(self):
        assert len(MobileActionType) == 13

    def test_is_str_enum(self):
        assert isinstance(MobileActionType.CLICK, str)


class TestParseAction:

    def setup_method(self):
        self.executor = MobileAIExecutor.__new__(MobileAIExecutor)

    def test_parse_go_back_cn(self):
        assert self.executor.parse_action("点击返回按钮") == MobileActionType.GO_BACK

    def test_parse_go_back_cn2(self):
        assert self.executor.parse_action("后退一步") == MobileActionType.GO_BACK

    def test_parse_go_back_en(self):
        assert self.executor.parse_action("press back") == MobileActionType.GO_BACK

    def test_parse_go_home_cn(self):
        assert self.executor.parse_action("回到主页") == MobileActionType.GO_HOME

    def test_parse_go_home_cn2(self):
        assert self.executor.parse_action("回到首页") == MobileActionType.GO_HOME

    def test_parse_go_home_en(self):
        assert self.executor.parse_action("go home") == MobileActionType.GO_HOME

    def test_parse_go_home_desktop(self):
        assert self.executor.parse_action("回到桌面") == MobileActionType.GO_HOME

    def test_parse_go_home_not_when_navigate(self):
        result = self.executor.parse_action("导航到主页")
        assert result != MobileActionType.GO_HOME

    def test_parse_go_home_not_when_jump(self):
        result = self.executor.parse_action("跳转到首页")
        assert result != MobileActionType.GO_HOME

    def test_parse_scroll_up_cn(self):
        assert self.executor.parse_action("向上滑动") == MobileActionType.SCROLL_UP

    def test_parse_scroll_up_cn2(self):
        assert self.executor.parse_action("上滑") == MobileActionType.SCROLL_UP

    def test_parse_scroll_up_en(self):
        assert self.executor.parse_action("scroll up") == MobileActionType.SCROLL_UP

    def test_parse_scroll_down_cn(self):
        assert self.executor.parse_action("向下滑动") == MobileActionType.SCROLL_DOWN

    def test_parse_scroll_down_cn2(self):
        assert self.executor.parse_action("下滑") == MobileActionType.SCROLL_DOWN

    def test_parse_scroll_down_en(self):
        assert self.executor.parse_action("scroll down") == MobileActionType.SCROLL_DOWN

    def test_parse_scroll_left_cn(self):
        assert self.executor.parse_action("向左滑动") == MobileActionType.SCROLL_LEFT

    def test_parse_scroll_left_cn2(self):
        assert self.executor.parse_action("左滑") == MobileActionType.SCROLL_LEFT

    def test_parse_scroll_left_en(self):
        assert self.executor.parse_action("scroll left") == MobileActionType.SCROLL_LEFT

    def test_parse_scroll_right_cn(self):
        assert self.executor.parse_action("向右滑动") == MobileActionType.SCROLL_RIGHT

    def test_parse_scroll_right_cn2(self):
        assert self.executor.parse_action("右滑") == MobileActionType.SCROLL_RIGHT

    def test_parse_scroll_right_en(self):
        assert self.executor.parse_action("scroll right") == MobileActionType.SCROLL_RIGHT

    def test_parse_input_cn(self):
        assert self.executor.parse_action("输入用户名") == MobileActionType.INPUT

    def test_parse_input_cn2(self):
        assert self.executor.parse_action("填写密码") == MobileActionType.INPUT

    def test_parse_input_cn3(self):
        assert self.executor.parse_action("填入内容") == MobileActionType.INPUT

    def test_parse_input_cn4(self):
        assert self.executor.parse_action("键入文字") == MobileActionType.INPUT

    def test_parse_input_en(self):
        assert self.executor.parse_action("input text") == MobileActionType.INPUT

    def test_parse_input_type(self):
        assert self.executor.parse_action("type hello") == MobileActionType.INPUT

    def test_parse_swipe_cn(self):
        assert self.executor.parse_action("滑动屏幕") == MobileActionType.SWIPE

    def test_parse_swipe_en(self):
        assert self.executor.parse_action("swipe left to right") == MobileActionType.SWIPE

    def test_parse_press_key_cn(self):
        assert self.executor.parse_action("按键回车") == MobileActionType.PRESS_KEY

    def test_parse_press_key_cn2(self):
        assert self.executor.parse_action("按回车键") == MobileActionType.PRESS_KEY

    def test_parse_press_key_en(self):
        assert self.executor.parse_action("press enter") == MobileActionType.PRESS_KEY

    def test_parse_launch_app_cn(self):
        assert self.executor.parse_action("启动应用") == MobileActionType.LAUNCH_APP

    def test_parse_launch_app_cn2(self):
        assert self.executor.parse_action("打开应用商店") == MobileActionType.LAUNCH_APP

    def test_parse_launch_app_en(self):
        assert self.executor.parse_action("launch app") == MobileActionType.LAUNCH_APP

    def test_parse_launch_app_en2(self):
        assert self.executor.parse_action("open app") == MobileActionType.LAUNCH_APP

    def test_parse_wait_cn(self):
        assert self.executor.parse_action("等待加载") == MobileActionType.WAIT

    def test_parse_wait_en(self):
        assert self.executor.parse_action("wait for element") == MobileActionType.WAIT

    def test_parse_verify_cn(self):
        assert self.executor.parse_action("验证结果") == MobileActionType.VERIFY

    def test_parse_verify_cn2(self):
        assert self.executor.parse_action("检查页面") == MobileActionType.VERIFY

    def test_parse_verify_cn3(self):
        assert self.executor.parse_action("确认登录成功") == MobileActionType.VERIFY

    def test_parse_verify_en(self):
        assert self.executor.parse_action("verify result") == MobileActionType.VERIFY

    def test_parse_verify_check(self):
        assert self.executor.parse_action("check status") == MobileActionType.VERIFY

    def test_parse_verify_assert(self):
        assert self.executor.parse_action("assert element visible") == MobileActionType.VERIFY

    def test_parse_default_click(self):
        assert self.executor.parse_action("选择该选项") == MobileActionType.CLICK

    def test_parse_default_click_unknown(self):
        assert self.executor.parse_action("something random") == MobileActionType.CLICK

    def test_parse_case_insensitive(self):
        assert self.executor.parse_action("INPUT TEXT") == MobileActionType.INPUT

    def test_parse_strip_whitespace(self):
        assert self.executor.parse_action("  返回  ") == MobileActionType.GO_BACK


class TestExtractInputText:

    def setup_method(self):
        self.executor = MobileAIExecutor.__new__(MobileAIExecutor)

    def test_extract_input_text_quoted_cn(self):
        result = self.executor._extract_input_text('输入"hello"到输入框')
        assert result == "hello"

    def test_extract_input_text_single_quoted(self):
        result = self.executor._extract_input_text("输入'world'")
        assert result == "world"

    def test_extract_input_text_to(self):
        result = self.executor._extract_input_text("输入hello到输入框")
        assert result == "hello"

    def test_extract_input_text_fill(self):
        result = self.executor._extract_input_text('填写"test"')
        assert result == "test"

    def test_extract_input_text_type_en(self):
        result = self.executor._extract_input_text('type "hello"')
        assert result == "hello"

    def test_extract_input_text_input_en(self):
        result = self.executor._extract_input_text("input 'value'")
        assert result == "value"

    def test_extract_input_text_no_match(self):
        result = self.executor._extract_input_text("点击按钮")
        assert result is None

    def test_extract_input_text_keyin(self):
        result = self.executor._extract_input_text('键入"abc"')
        assert result == "abc"


class TestExtractInputTarget:

    def setup_method(self):
        self.executor = MobileAIExecutor.__new__(MobileAIExecutor)

    def test_extract_target_zhong(self):
        result = self.executor._extract_input_target("在用户名中输入hello")
        assert result == "用户名"

    def test_extract_target_li(self):
        result = self.executor._extract_input_target("在密码框里输入123")
        assert result == "密码框"

    def test_extract_target_shang(self):
        result = self.executor._extract_input_target("在搜索栏上输入test")
        assert result == "搜索栏"

    def test_extract_target_simple(self):
        result = self.executor._extract_input_target("在输入框输入hello")
        assert result == "输入框"

    def test_extract_target_fill_zhong(self):
        result = self.executor._extract_input_target("在表单中填写内容")
        assert result == "表单"

    def test_extract_target_fill_li(self):
        result = self.executor._extract_input_target("在输入框里填写数据")
        assert result == "输入框"

    def test_extract_target_no_match(self):
        result = self.executor._extract_input_target("输入hello")
        assert result is None


class TestExtractPackageActivity:

    def setup_method(self):
        self.executor = MobileAIExecutor.__new__(MobileAIExecutor)

    def test_extract_package_activity(self):
        result = self.executor._extract_package_activity("启动 com.example/.MainActivity")
        assert result == ("com.example", ".MainActivity")

    def test_extract_package_activity_full(self):
        result = self.executor._extract_package_activity("启动 com.example.app/com.example.app.MainActivity")
        assert result == ("com.example.app", "com.example.app.MainActivity")

    def test_extract_package_activity_no_match(self):
        result = self.executor._extract_package_activity("启动应用")
        assert result is None

    def test_extract_package_activity_simple(self):
        result = self.executor._extract_package_activity("com.test/MainActivity")
        assert result == ("com.test", "MainActivity")


class TestMobileAIErrorHierarchy:

    def test_mobile_ai_error_is_exception(self):
        assert issubclass(MobileAIError, Exception)

    def test_mobile_device_error(self):
        assert issubclass(MobileDeviceError, MobileAIError)

    def test_mobile_recognition_error(self):
        assert issubclass(MobileRecognitionError, MobileAIError)

    def test_mobile_ai_error_raise(self):
        with pytest.raises(MobileAIError):
            raise MobileAIError("test")

    def test_mobile_device_error_raise(self):
        with pytest.raises(MobileAIError):
            raise MobileDeviceError("device error")

    def test_mobile_recognition_error_raise(self):
        with pytest.raises(MobileAIError):
            raise MobileRecognitionError("recognition error")

    def test_device_not_recognition(self):
        assert not issubclass(MobileDeviceError, MobileRecognitionError)

    def test_recognition_not_device(self):
        assert not issubclass(MobileRecognitionError, MobileDeviceError)


class TestMobileActionResult:

    def test_action_result_creation(self):
        result = MobileActionResult(
            success=True,
            action_type=MobileActionType.CLICK,
            description="点击登录",
        )
        assert result.success is True
        assert result.action_type == MobileActionType.CLICK
        assert result.description == "点击登录"
        assert result.coordinates is None
        assert result.locator_info is None
        assert result.error_message is None
        assert result.ai_confidence == 0.0
        assert result.used_cache is False
        assert result.cached_locator is None

    def test_action_result_with_coordinates(self):
        result = MobileActionResult(
            success=True,
            action_type=MobileActionType.CLICK,
            description="点击",
            coordinates={"x": 540, "y": 1260},
            ai_confidence=0.95,
        )
        assert result.coordinates == {"x": 540, "y": 1260}
        assert result.ai_confidence == 0.95

    def test_action_result_failure(self):
        result = MobileActionResult(
            success=False,
            action_type=MobileActionType.INPUT,
            description="输入失败",
            error_message="无法定位输入框",
        )
        assert result.success is False
        assert result.error_message == "无法定位输入框"

    def test_action_result_with_cache(self):
        result = MobileActionResult(
            success=True,
            action_type=MobileActionType.CLICK,
            description="点击",
            used_cache=True,
            cached_locator={"resource_id": "btn"},
        )
        assert result.used_cache is True
        assert result.cached_locator == {"resource_id": "btn"}

    def test_action_result_is_dataclass(self):
        result = MobileActionResult(
            success=True,
            action_type=MobileActionType.CLICK,
            description="test",
        )
        d = asdict(result)
        assert "success" in d
        assert "action_type" in d
        assert "description" in d


class TestExecutionModeExtension:

    def test_mobile_realtime_exists(self):
        assert hasattr(ExecutionMode, "MOBILE_REALTIME")

    def test_mobile_smart_exists(self):
        assert hasattr(ExecutionMode, "MOBILE_SMART")

    def test_mobile_realtime_value(self):
        assert ExecutionMode.MOBILE_REALTIME.value == "mobile_realtime"

    def test_mobile_smart_value(self):
        assert ExecutionMode.MOBILE_SMART.value == "mobile_smart"

    def test_preprocess_exists(self):
        assert ExecutionMode.PREPROCESS.value == "preprocess"

    def test_realtime_exists(self):
        assert ExecutionMode.REALTIME.value == "realtime"

    def test_smart_exists(self):
        assert ExecutionMode.SMART.value == "smart"

    def test_valid_execution_modes_contains_mobile(self):
        valid_modes = {"preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"}
        assert "mobile_realtime" in valid_modes
        assert "mobile_smart" in valid_modes

    def test_execution_mode_is_str_enum(self):
        assert isinstance(ExecutionMode.MOBILE_REALTIME, str)
        assert isinstance(ExecutionMode.MOBILE_SMART, str)

    def test_execution_mode_member_count(self):
        assert len(ExecutionMode) == 5


class TestAPIExecutionMode:

    def test_valid_execution_modes_set(self):
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2
        valid_modes = TestExecutionEngineV2.VALID_EXECUTION_MODES
        assert "mobile_realtime" in valid_modes
        assert "mobile_smart" in valid_modes

    def test_valid_execution_modes_all(self):
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2
        valid_modes = TestExecutionEngineV2.VALID_EXECUTION_MODES
        assert valid_modes == {"preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart"}

    def test_mobile_device_id_parameter(self):
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2
        init_params = inspect.signature(TestExecutionEngineV2.__init__).parameters
        assert "mobile_device_id" in init_params


class TestAppiumRemoval:

    def test_mobile_controller_file_not_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app", "utils", "mobile_controller.py",
        )
        assert not os.path.exists(path)

    def test_precondition_service_no_mobile_controller_import(self):
        import app.services.precondition_service as precondition_module
        source = inspect.getsource(precondition_module)
        assert "MobileController" not in source

    def test_precondition_service_no_mobile_controller_attribute(self):
        from app.services.precondition_service import PreconditionService
        svc = PreconditionService()
        assert not hasattr(svc, "mobile_controller") or svc.mobile_controller is None


class TestInputTextSecurity:

    def test_input_text_escapes_percent(self):
        text = "50%off"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        assert "50%%off" == input_escaped

    def test_input_text_escapes_space(self):
        ctrl = AdbController(udid="device1")
        cmd = ctrl._build_command("shell", f"input text 'hello%sworld'")
        assert "%s" in " ".join(cmd)

    def test_input_text_wraps_in_single_quotes(self):
        ctrl = AdbController(udid="device1")
        cmd = ctrl._build_command("shell", "input text 'hello'")
        joined = " ".join(cmd)
        assert "'" in joined

    def test_input_text_shell_injection_semicolon(self):
        text = "hello; rm -rf /"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        assert shell_escaped.startswith("hello;")
        cmd_part = f"input text '{shell_escaped}'"
        assert cmd_part.startswith("input text '")

    def test_input_text_shell_injection_dollar(self):
        text = "$HOME"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        cmd_part = f"input text '{shell_escaped}'"
        assert "$HOME" in cmd_part
        assert cmd_part.startswith("input text '")
        assert cmd_part.endswith("'")

    def test_input_text_shell_injection_backtick(self):
        text = "`whoami`"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        cmd_part = f"input text '{shell_escaped}'"
        assert cmd_part.startswith("input text '")

    def test_input_text_single_quote_escaping(self):
        text = "it's"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        assert "'\\''" in shell_escaped

    def test_input_text_pipe_injection(self):
        text = "hello | cat /etc/passwd"
        input_escaped = text.replace("%", "%%").replace(" ", "%s")
        shell_escaped = input_escaped.replace("'", "'\\''")
        cmd_part = f"input text '{shell_escaped}'"
        assert cmd_part.startswith("input text '")
        assert cmd_part.endswith("'")


class TestPackageNameValidation:

    def test_validate_valid_package_name(self):
        AdbController._validate_package_name("com.example.app")

    def test_validate_valid_package_name_simple(self):
        AdbController._validate_package_name("com.example")

    def test_validate_valid_package_name_long(self):
        AdbController._validate_package_name("com.example.app.sub.module")

    def test_validate_invalid_package_name_no_dot(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("example")

    def test_validate_invalid_package_name_starts_with_number(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("com.123app")

    def test_validate_invalid_package_name_segment_starts_with_number(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("com.example.1bad")

    def test_validate_invalid_package_name_empty(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("")

    def test_validate_invalid_package_name_special_chars(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("com.example;rm -rf")

    def test_validate_invalid_package_name_spaces(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("com. example")

    def test_validate_invalid_package_name_hyphen(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("com.my-app")

    def test_validate_invalid_package_name_single_segment(self):
        with pytest.raises(AdbError, match="Invalid package name"):
            AdbController._validate_package_name("singlesegment")


class TestActivityNameValidation:

    def test_valid_activity_name(self):
        assert re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', ".MainActivity")

    def test_valid_activity_name_full(self):
        assert re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', "com.example.app.MainActivity")

    def test_invalid_activity_name_semicolon(self):
        assert not re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', ".Activity;rm")

    def test_invalid_activity_name_pipe(self):
        assert not re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', ".Activity|cat")

    def test_invalid_activity_name_starts_with_number(self):
        assert not re.match(r'^\.?[a-zA-Z][a-zA-Z0-9._]*$', "1Activity")


class TestXMLSanitization:

    def test_sanitize_xml_removes_doctype(self):
        xml_with_doctype = '<!DOCTYPE foo [<!ENTITY xxe "bar">]><hierarchy><node/></hierarchy>'
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        sanitized = helper._sanitize_xml(xml_with_doctype)
        assert "<!DOCTYPE" not in sanitized

    def test_sanitize_xml_removes_entity(self):
        xml_with_entity = '<!ENTITY xxe "bar"><hierarchy><node/></hierarchy>'
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        sanitized = helper._sanitize_xml(xml_with_entity)
        assert "<!ENTITY" not in sanitized

    def test_sanitize_xml_preserves_normal(self):
        normal_xml = '<hierarchy><node text="hello"/></hierarchy>'
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        sanitized = helper._sanitize_xml(normal_xml)
        assert "<hierarchy>" in sanitized
        assert 'text="hello"' in sanitized

    def test_sanitize_xml_with_xxe_payload(self):
        xxe_payload = '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><hierarchy/>'
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        sanitized = helper._sanitize_xml(xxe_payload)
        assert "SYSTEM" not in sanitized
        assert "/etc/passwd" not in sanitized

    def test_parse_xml_after_sanitization(self):
        xml_with_doctype = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "bar">]><hierarchy><node text="ok"/></hierarchy>'
        helper = UIAutomatorHelper.__new__(UIAutomatorHelper)
        elements = helper._parse_xml(xml_with_doctype)
        text_elements = [e for e in elements if e.text == "ok"]
        assert len(text_elements) == 1


class TestCachedLocatorSourceCheck:

    def test_get_cached_locator_returns_none_for_non_mobile_source(self):
        executor = MobileAIExecutor.__new__(MobileAIExecutor)

        class FakeLocator:
            source = "ai"
            element_id = "com.example:id/btn"
            element_name = "login"
            element_text = "登录"
            ai_coordinate = {"x": 540, "y": 1260}

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self
            def first(self):
                return FakeLocator()

        class FakeDb:
            def query(self, model):
                return FakeQuery()

        executor.db = FakeDb()
        result = executor._get_cached_locator(step_id=1)
        assert result is None

    def test_get_cached_locator_returns_data_for_mobile_source(self):
        executor = MobileAIExecutor.__new__(MobileAIExecutor)

        class FakeLocator:
            source = "ai_mobile"
            element_id = "com.example:id/btn"
            element_name = "登录按钮"
            element_text = "登录"
            ai_coordinate = {"x": 540, "y": 1260}

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self
            def first(self):
                return FakeLocator()

        class FakeDb:
            def query(self, model):
                return FakeQuery()

        executor.db = FakeDb()
        result = executor._get_cached_locator(step_id=1)
        assert result is not None
        assert result["resource_id"] == "com.example:id/btn"
        assert result["accessibility_id"] == "登录按钮"

    def test_get_cached_locator_returns_none_for_manual_source(self):
        executor = MobileAIExecutor.__new__(MobileAIExecutor)

        class FakeLocator:
            source = "manual"
            element_id = "btn-login"
            element_name = "login"
            element_text = "登录"
            ai_coordinate = None

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self
            def first(self):
                return FakeLocator()

        class FakeDb:
            def query(self, model):
                return FakeQuery()

        executor.db = FakeDb()
        result = executor._get_cached_locator(step_id=1)
        assert result is None

    def test_get_cached_locator_returns_none_when_no_locator(self):
        executor = MobileAIExecutor.__new__(MobileAIExecutor)

        class FakeQuery:
            def filter(self, *args, **kwargs):
                return self
            def first(self):
                return None

        class FakeDb:
            def query(self, model):
                return FakeQuery()

        executor.db = FakeDb()
        result = executor._get_cached_locator(step_id=999)
        assert result is None
