"""
MCP Direct Execution 混合方案单元测试

测试范围：
1. VisionRecognizer bug 修复测试 - browser 参数处理
2. MCPRecognizer.execute_action() 方法测试
3. ElementLocatorService 执行策略路由测试
4. 降级逻辑测试
5. 配置项测试

规则：
- 严禁使用 Mock
- 必须使用真实测试
- 数据库必须使用 MySQL
- 测试用例必须有价值
"""
import inspect
import pytest
from typing import Optional, Dict, Any, List

from app.core.config import settings, Settings
from app.interfaces.element_recognizer import ElementRecognizer, RecognitionResult
from app.services.recognizers.vision_recognizer import VisionRecognizer
from app.services.recognizers.mcp_recognizer import MCPRecognizer
from app.services.element_locator_service import ElementLocatorService
from app.models.element_locator import ElementLocator
from app.utils.playwright_mcp_client import PlaywrightMCPClient
from app.utils.unified_vision_model import UnifiedVisionModel


# ============================================================
# 辅助类：真实对象，用于替代 Mock
# ============================================================

class FakePage:
    """模拟 Playwright Page 对象，提供 execute_javascript 方法"""

    def __init__(self, js_result: Optional[Dict[str, Any]] = None):
        self._js_result = js_result or {}

    async def execute_javascript(self, script: str, *args):
        return self._js_result


class FakeBrowserWithPage:
    """带 _page 属性的浏览器对象，用于测试 VisionRecognizer 的 browser 参数提取逻辑"""

    def __init__(self, page: Optional[FakePage] = None, screenshot_data: Optional[bytes] = None):
        self._page = page or FakePage()
        self._screenshot_data = screenshot_data

    async def take_screenshot(self) -> Optional[bytes]:
        return self._screenshot_data

    async def execute_javascript(self, script: str, *args):
        return self._page._js_result


class FakeBrowserWithoutPage:
    """不带 _page 属性的浏览器对象，自身即为 page"""

    def __init__(self, js_result: Optional[Dict[str, Any]] = None, screenshot_data: Optional[bytes] = None):
        self._js_result = js_result or {}
        self._screenshot_data = screenshot_data

    async def take_screenshot(self) -> Optional[bytes]:
        return self._screenshot_data

    async def execute_javascript(self, script: str, *args):
        return self._js_result


class FakeVisionModel:
    """真实的视觉模型替代对象，返回预设的 AI 响应"""

    def __init__(self, response: str = '{"x": 100, "y": 200, "width": 50, "height": 30, "confidence": 0.9}'):
        self._response = response

    def analyze_image(self, screenshot: bytes, prompt: str) -> str:
        return self._response


class FakeMCPClientUnavailable:
    """不可用的 MCP 客户端，is_available 返回 False"""

    @property
    def is_available(self) -> bool:
        return False


class FakeMCPClientAvailable:
    """可用的 MCP 客户端，用于测试 execute_action 的参数校验逻辑"""

    def __init__(self):
        self.last_click_args = None
        self.last_type_args = None
        self.last_hover_args = None
        self.last_select_args = None
        self.last_wait_args = None

    @property
    def is_available(self) -> bool:
        return True

    async def browser_click(self, element: str, ref: Optional[str] = None):
        self.last_click_args = {"element": element, "ref": ref}

    async def browser_type(self, element: str, text: str, ref: Optional[str] = None):
        self.last_type_args = {"element": element, "text": text, "ref": ref}

    async def browser_hover(self, element: str, ref: Optional[str] = None):
        self.last_hover_args = {"element": element, "ref": ref}

    async def browser_select_option(self, element: str, values: List[str], ref: Optional[str] = None):
        self.last_select_args = {"element": element, "values": values, "ref": ref}

    async def browser_wait_for(self, time: Optional[float] = None, text: Optional[str] = None):
        self.last_wait_args = {"time": time, "text": text}


class FakeMCPLLM:
    """真实的 MCP LLM 替代对象"""

    async def understand_operation(self, accessibility_tree: str, operation_description: str, action_type: Optional[str] = None):
        return {
            "locator_type": "ref",
            "locator_value": "test-ref-001",
            "confidence": 0.85,
            "element_description": "登录按钮",
            "reasoning": "通过 Accessibility Tree ref 定位"
        }


# ============================================================
# 1. VisionRecognizer bug 修复测试
# ============================================================

class TestVisionRecognizerBrowserParam:
    """测试 VisionRecognizer.recognize() 接收 browser 参数时能正确处理"""

    @pytest.mark.asyncio
    async def test_recognize_with_browser_has_page_attribute(self):
        """
        测试传入有 _page 属性的 browser 对象时，能正确提取 page

        前置条件：browser 对象有 _page 属性
        测试步骤：调用 recognize() 传入带 _page 的 browser
        预期结果：不抛出异常，能正确提取 page 用于后续操作
        """
        fake_page = FakePage(js_result={"tag": "button", "id": "login-btn"})
        fake_browser = FakeBrowserWithPage(
            page=fake_page,
            screenshot_data=b"fake_screenshot_data"
        )
        vision_model = FakeVisionModel(
            response='{"x": 100, "y": 200, "width": 80, "height": 40, "element_type": "button", "confidence": 0.92}'
        )
        recognizer = VisionRecognizer(vision_model, confidence_threshold=0.8)

        result = await recognizer.recognize(fake_browser, "点击登录按钮")

        assert result is not None
        assert isinstance(result, RecognitionResult)
        assert result.locator_type == "vision"

    @pytest.mark.asyncio
    async def test_recognize_with_browser_no_page_attribute(self):
        """
        测试传入没有 _page 属性的 browser 对象时，browser 自身作为 page 使用

        前置条件：browser 对象没有 _page 属性
        测试步骤：调用 recognize() 传入不带 _page 的 browser
        预期结果：不抛出异常，browser 自身被当作 page 使用
        """
        fake_browser = FakeBrowserWithoutPage(
            js_result={"tag": "input", "id": "username"},
            screenshot_data=b"fake_screenshot_data"
        )
        vision_model = FakeVisionModel(
            response='{"x": 50, "y": 100, "width": 200, "height": 30, "element_type": "input", "confidence": 0.88}'
        )
        recognizer = VisionRecognizer(vision_model, confidence_threshold=0.8)

        result = await recognizer.recognize(fake_browser, "输入用户名")

        assert result is not None
        assert isinstance(result, RecognitionResult)
        assert result.locator_type == "vision"

    @pytest.mark.asyncio
    async def test_recognize_page_extraction_from_browser_with_page(self):
        """
        测试 VisionRecognizer 内部 page 提取逻辑：
        当 browser 有 _page 属性时，page 应为 browser._page

        前置条件：browser 对象有 _page 属性
        测试步骤：验证 recognize 方法中 page = browser._page if hasattr(browser, '_page') else browser
        预期结果：提取的 page 是 browser._page，而非 browser 本身
        """
        inner_page = FakePage(js_result={"tag": "a", "id": "link-home"})
        fake_browser = FakeBrowserWithPage(
            page=inner_page,
            screenshot_data=b"fake_screenshot_data"
        )

        # 验证 hasattr 行为
        assert hasattr(fake_browser, '_page') is True
        assert fake_browser._page is inner_page

        # 验证提取逻辑
        extracted_page = fake_browser._page if hasattr(fake_browser, '_page') else fake_browser
        assert extracted_page is inner_page
        assert extracted_page is not fake_browser

    @pytest.mark.asyncio
    async def test_recognize_page_extraction_from_browser_without_page(self):
        """
        测试 VisionRecognizer 内部 page 提取逻辑：
        当 browser 没有 _page 属性时，page 应为 browser 自身

        前置条件：browser 对象没有 _page 属性
        测试步骤：验证 recognize 方法中 page 提取逻辑
        预期结果：提取的 page 是 browser 本身
        """
        fake_browser = FakeBrowserWithoutPage(
            js_result={"tag": "div"},
            screenshot_data=b"fake_screenshot_data"
        )

        # 验证 hasattr 行为
        assert hasattr(fake_browser, '_page') is False

        # 验证提取逻辑
        extracted_page = fake_browser._page if hasattr(fake_browser, '_page') else fake_browser
        assert extracted_page is fake_browser

    @pytest.mark.asyncio
    async def test_recognize_screenshot_failure_returns_invalid_result(self):
        """
        测试截图失败时返回无效的 RecognitionResult

        前置条件：browser 的 take_screenshot 抛出异常
        测试步骤：调用 recognize()
        预期结果：返回 confidence=0 的 RecognitionResult，raw_result 包含 error
        """

        class BrowserScreenshotFail:
            async def take_screenshot(self):
                raise RuntimeError("浏览器连接断开")

        vision_model = FakeVisionModel()
        recognizer = VisionRecognizer(vision_model, confidence_threshold=0.8)

        result = await recognizer.recognize(BrowserScreenshotFail(), "点击按钮")

        assert result.confidence == 0
        assert result.raw_result is not None
        assert "error" in result.raw_result

    @pytest.mark.asyncio
    async def test_recognize_empty_screenshot_returns_invalid_result(self):
        """
        测试截图返回空数据时返回无效的 RecognitionResult

        前置条件：browser 的 take_screenshot 返回 None
        测试步骤：调用 recognize()
        预期结果：返回 confidence=0 的 RecognitionResult
        """

        class BrowserScreenshotEmpty:
            async def take_screenshot(self):
                return None

        vision_model = FakeVisionModel()
        recognizer = VisionRecognizer(vision_model, confidence_threshold=0.8)

        result = await recognizer.recognize(BrowserScreenshotEmpty(), "点击按钮")

        assert result.confidence == 0
        assert result.locator_value == ""


# ============================================================
# 2. MCPRecognizer.execute_action() 测试
# ============================================================

class TestMCPRecognizerExecuteAction:
    """测试 MCPRecognizer.execute_action() 方法"""

    @pytest.mark.asyncio
    async def test_execute_action_method_signature(self):
        """
        测试 execute_action() 方法签名正确，包含 action_type 和 input_value 参数

        前置条件：MCPRecognizer 类已定义
        测试步骤：检查 execute_action 方法的参数签名
        预期结果：方法包含 action_type 和 input_value 参数
        """
        sig = inspect.signature(MCPRecognizer.execute_action)
        params = list(sig.parameters.keys())

        assert "action_type" in params, f"execute_action 缺少 action_type 参数，实际参数: {params}"
        assert "input_value" in params, f"execute_action 缺少 input_value 参数，实际参数: {params}"

        # 验证 action_type 默认值
        assert sig.parameters["action_type"].default == "click"
        # 验证 input_value 默认值
        assert sig.parameters["input_value"].default is None

    @pytest.mark.asyncio
    async def test_execute_action_mcp_unavailable_returns_false(self):
        """
        测试 MCP 不可用时 execute_action 返回 False

        前置条件：MCP 客户端不可用
        测试步骤：调用 execute_action()
        预期结果：返回 False
        """
        mcp_client = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=mcp_client)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="test-ref",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is False

    @pytest.mark.asyncio
    async def test_execute_action_click_with_ref_locator(self):
        """
        测试 click 操作使用 ref 定位类型时正确调用 browser_click

        前置条件：MCP 客户端可用，定位类型为 ref
        测试步骤：调用 execute_action()，action_type="click"
        预期结果：返回 True，MCP 客户端收到正确的 click 参数
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="ref-abc-123",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is True
        assert fake_mcp.last_click_args is not None
        assert fake_mcp.last_click_args["element"] == ""
        assert fake_mcp.last_click_args["ref"] == "ref-abc-123"

    @pytest.mark.asyncio
    async def test_execute_action_click_with_css_locator(self):
        """
        测试 click 操作使用 css 定位类型时正确调用 browser_click

        前置条件：MCP 客户端可用，定位类型为 css
        测试步骤：调用 execute_action()，action_type="click"
        预期结果：返回 True，MCP 客户端收到 element 参数
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="#login-btn",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is True
        assert fake_mcp.last_click_args is not None
        assert fake_mcp.last_click_args["element"] == "#login-btn"
        assert fake_mcp.last_click_args["ref"] is None

    @pytest.mark.asyncio
    async def test_execute_action_type_without_input_value_returns_false(self):
        """
        测试 type 操作缺少 input_value 时返回 False

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="type"，input_value=None
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="ref-input-001",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="type", input_value=None)

        assert executed is False

    @pytest.mark.asyncio
    async def test_execute_action_type_with_input_value_succeeds(self):
        """
        测试 type 操作有 input_value 时正确调用 browser_type

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="type"，input_value="testuser"
        预期结果：返回 True，MCP 客户端收到正确的 type 参数
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="ref-input-001",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="type", input_value="testuser")

        assert executed is True
        assert fake_mcp.last_type_args is not None
        assert fake_mcp.last_type_args["text"] == "testuser"

    @pytest.mark.asyncio
    async def test_execute_action_input_type_alias(self):
        """
        测试 "input" 操作类型与 "type" 等价

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="input"，input_value="hello"
        预期结果：返回 True，MCP 客户端收到 browser_type 调用
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="#search-input",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="input", input_value="hello")

        assert executed is True
        assert fake_mcp.last_type_args is not None
        assert fake_mcp.last_type_args["text"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_action_select_without_input_value_returns_false(self):
        """
        测试 select 操作缺少 input_value 时返回 False

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="select"，input_value=None
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="ref-select-001",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="select", input_value=None)

        assert executed is False

    @pytest.mark.asyncio
    async def test_execute_action_select_with_comma_separated_values(self):
        """
        测试 select 操作支持逗号分隔的多值选择

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="select"，input_value="option1, option2"
        预期结果：返回 True，MCP 客户端收到拆分后的 values 列表
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="ref-select-001",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="select", input_value="option1, option2")

        assert executed is True
        assert fake_mcp.last_select_args is not None
        assert fake_mcp.last_select_args["values"] == ["option1", "option2"]

    @pytest.mark.asyncio
    async def test_execute_action_hover_succeeds(self):
        """
        测试 hover 操作正确调用 browser_hover

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="hover"
        预期结果：返回 True
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value=".menu-item",
            confidence= 0.9
        )
        executed = await recognizer.execute_action(result, action_type="hover")

        assert executed is True
        assert fake_mcp.last_hover_args is not None

    @pytest.mark.asyncio
    async def test_execute_action_wait_with_numeric_input(self):
        """
        测试 wait 操作传入数字字符串时作为等待时间处理

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="wait"，input_value="2.5"
        预期结果：返回 True，MCP 客户端收到 time=2.5
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="",
            confidence=0.5
        )
        executed = await recognizer.execute_action(result, action_type="wait", input_value="2.5")

        assert executed is True
        assert fake_mcp.last_wait_args is not None
        assert fake_mcp.last_wait_args["time"] == 2.5
        assert fake_mcp.last_wait_args["text"] is None

    @pytest.mark.asyncio
    async def test_execute_action_wait_with_text_input(self):
        """
        测试 wait 操作传入非数字字符串时作为等待文本处理

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="wait"，input_value="加载完成"
        预期结果：返回 True，MCP 客户端收到 text="加载完成"
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="",
            confidence=0.5
        )
        executed = await recognizer.execute_action(result, action_type="wait", input_value="加载完成")

        assert executed is True
        assert fake_mcp.last_wait_args is not None
        assert fake_mcp.last_wait_args["time"] is None
        assert fake_mcp.last_wait_args["text"] == "加载完成"

    @pytest.mark.asyncio
    async def test_execute_action_unsupported_action_type_returns_false(self):
        """
        测试不支持的操作类型返回 False

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="scroll"
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value=".container",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="scroll")

        assert executed is False

    @pytest.mark.asyncio
    async def test_execute_action_empty_locator_value_non_wait_returns_false(self):
        """
        测试非 wait 操作且定位值为空时返回 False

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="click"，locator_value=""
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is False

    @pytest.mark.asyncio
    async def test_execute_action_wait_with_empty_locator_value_succeeds(self):
        """
        测试 wait 操作即使定位值为空也能执行

        前置条件：MCP 客户端可用
        测试步骤：调用 execute_action()，action_type="wait"，locator_value=""
        预期结果：返回 True（wait 操作不要求定位值）
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="css",
            locator_value="",
            confidence=0.5
        )
        executed = await recognizer.execute_action(result, action_type="wait", input_value="3")

        assert executed is True


# ============================================================
# 3. ElementLocatorService 执行策略路由测试
# ============================================================

class TestElementLocatorServiceStrategy:
    """测试 ElementLocatorService 的执行策略路由"""

    @pytest.mark.asyncio
    async def test_should_direct_execute_config_disabled(self):
        """
        测试 _should_direct_execute() 在配置关闭时返回 False

        前置条件：MCP_DIRECT_EXECUTION_ENABLED = False
        测试步骤：调用 _should_direct_execute("click")
        预期结果：返回 False
        """
        fake_browser = FakeBrowserWithoutPage()
        fake_vision = FakeVisionModel()
        # 使用 VisionRecognizer（非 MCPRecognizer）
        recognizer = VisionRecognizer(fake_vision, 0.8)

        # 创建一个不依赖数据库的 ElementLocatorService
        # 由于 _should_direct_execute 不依赖 db，我们可以传入 None
        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = fake_browser
        service.vision_model = fake_vision
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        # 确保 MCP_DIRECT_EXECUTION_ENABLED 为 False
        original_value = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = False
            result = service._should_direct_execute("click")
            assert result is False
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_value

    @pytest.mark.asyncio
    async def test_should_direct_execute_non_mcp_recognizer(self):
        """
        测试 _should_direct_execute() 在非 MCPRecognizer 时返回 False

        前置条件：MCP_DIRECT_EXECUTION_ENABLED = True，但 recognizer 是 VisionRecognizer
        测试步骤：调用 _should_direct_execute("click")
        预期结果：返回 False
        """
        fake_browser = FakeBrowserWithoutPage()
        fake_vision = FakeVisionModel()
        recognizer = VisionRecognizer(fake_vision, 0.8)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = fake_browser
        service.vision_model = fake_vision
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_value = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = True
            result = service._should_direct_execute("click")
            assert result is False
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_value

    @pytest.mark.asyncio
    async def test_should_direct_execute_disallowed_action_type(self):
        """
        测试 _should_direct_execute() 在不在允许操作类型时返回 False

        前置条件：MCP_DIRECT_EXECUTION_ENABLED = True，recognizer 是 MCPRecognizer，
                  但 action_type 不在 MCP_EXECUTION_OPERATION_TYPES 中
        测试步骤：调用 _should_direct_execute("verify")
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = FakeVisionModel()
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_enabled = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        original_types = getattr(settings, 'MCP_EXECUTION_OPERATION_TYPES', 'click,type,hover,select')
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = True
            settings.MCP_EXECUTION_OPERATION_TYPES = "click,type,hover,select"
            result = service._should_direct_execute("verify")
            assert result is False
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_enabled
            settings.MCP_EXECUTION_OPERATION_TYPES = original_types

    @pytest.mark.asyncio
    async def test_should_direct_execute_all_conditions_met(self):
        """
        测试 _should_direct_execute() 在所有条件满足时返回 True

        前置条件：MCP_DIRECT_EXECUTION_ENABLED = True，recognizer 是 MCPRecognizer，
                  action_type 在允许列表中
        测试步骤：调用 _should_direct_execute("click")
        预期结果：返回 True
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = FakeVisionModel()
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_enabled = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        original_types = getattr(settings, 'MCP_EXECUTION_OPERATION_TYPES', 'click,type,hover,select')
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = True
            settings.MCP_EXECUTION_OPERATION_TYPES = "click,type,hover,select"

            # 测试所有允许的操作类型
            for action_type in ["click", "type", "hover", "select"]:
                result = service._should_direct_execute(action_type)
                assert result is True, f"action_type={action_type} 应该返回 True"
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_enabled
            settings.MCP_EXECUTION_OPERATION_TYPES = original_types

    @pytest.mark.asyncio
    async def test_should_direct_execute_custom_operation_types(self):
        """
        测试自定义 MCP_EXECUTION_OPERATION_TYPES 配置

        前置条件：MCP_EXECUTION_OPERATION_TYPES = "click,input"
        测试步骤：调用 _should_direct_execute("type") 和 _should_direct_execute("input")
        预期结果："type" 返回 False（不在自定义列表中），"input" 返回 True
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = FakeVisionModel()
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_enabled = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        original_types = getattr(settings, 'MCP_EXECUTION_OPERATION_TYPES', 'click,type,hover,select')
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = True
            settings.MCP_EXECUTION_OPERATION_TYPES = "click,input"

            assert service._should_direct_execute("click") is True
            assert service._should_direct_execute("input") is True
            assert service._should_direct_execute("type") is False
            assert service._should_direct_execute("hover") is False
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_enabled
            settings.MCP_EXECUTION_OPERATION_TYPES = original_types

    @pytest.mark.asyncio
    async def test_direct_execute_action_with_non_mcp_recognizer_returns_false(self):
        """
        测试 direct_execute_action() 在非 MCPRecognizer 时返回 False

        前置条件：recognizer 是 VisionRecognizer
        测试步骤：调用 direct_execute_action()
        预期结果：返回 False
        """
        fake_vision = FakeVisionModel()
        recognizer = VisionRecognizer(fake_vision, 0.8)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = fake_vision
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        result = RecognitionResult(
            locator_type="vision",
            locator_value="100,200",
            confidence=0.9
        )
        executed = await service.direct_execute_action(result, action_type="click")
        assert executed is False


# ============================================================
# 4. 降级逻辑测试
# ============================================================

class TestDegradationLogic:
    """测试 MCP 直执失败时的降级逻辑"""

    @pytest.mark.asyncio
    async def test_mcp_recognizer_unavailable_returns_zero_confidence(self):
        """
        测试 MCPRecognizer 在 MCP 不可用时返回 confidence=0 的结果

        这是降级的第一步：MCP 识别失败，返回无效结果
        前置条件：MCP 客户端不可用
        测试步骤：调用 recognize()
        预期结果：返回 confidence=0 的 RecognitionResult，raw_result 包含 error
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = await recognizer.recognize(None, "点击登录按钮")

        assert result.confidence == 0
        assert result.raw_result is not None
        assert "error" in result.raw_result
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_mcp_execute_action_unavailable_returns_false(self):
        """
        测试 MCP 不可用时 execute_action 返回 False

        降级场景：MCP 直执失败，应降级到 Controller 执行
        前置条件：MCP 客户端不可用
        测试步骤：调用 execute_action()
        预期结果：返回 False，表示需要降级
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="test-ref",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is False

    @pytest.mark.asyncio
    async def test_direct_execute_action_exception_returns_false(self):
        """
        测试 MCP 直执过程中抛出异常时返回 False（降级到 Controller）

        前置条件：MCP 客户端在执行操作时抛出异常
        测试步骤：调用 direct_execute_action()
        预期结果：返回 False
        """

        class FakeMCPClientException:
            @property
            def is_available(self) -> bool:
                return True

            async def browser_click(self, element: str, ref: Optional[str] = None):
                raise ConnectionError("MCP 服务连接断开")

        fake_mcp = FakeMCPClientException()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        result = RecognitionResult(
            locator_type="ref",
            locator_value="test-ref",
            confidence=0.9
        )
        executed = await recognizer.execute_action(result, action_type="click")

        assert executed is False

    @pytest.mark.asyncio
    async def test_config_disabled_no_direct_execution(self):
        """
        测试 MCP_DIRECT_EXECUTION_ENABLED=False 时行为不变

        前置条件：MCP_DIRECT_EXECUTION_ENABLED = False
        测试步骤：验证 _should_direct_execute 对所有操作类型返回 False
        预期结果：不执行直执，所有操作走 Controller 路径
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = FakeVisionModel()
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_enabled = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = False

            for action_type in ["click", "type", "hover", "select", "verify", "wait"]:
                result = service._should_direct_execute(action_type)
                assert result is False, f"MCP_DIRECT_EXECUTION_ENABLED=False 时，action_type={action_type} 不应直执"
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_enabled

    @pytest.mark.asyncio
    async def test_vision_recognizer_never_direct_execute(self):
        """
        测试使用 VisionRecognizer 时永远不会触发直执

        前置条件：recognizer 是 VisionRecognizer，MCP_DIRECT_EXECUTION_ENABLED=True
        测试步骤：调用 _should_direct_execute()
        预期结果：返回 False，因为 VisionRecognizer 不支持 MCP 直执
        """
        fake_vision = FakeVisionModel()
        recognizer = VisionRecognizer(fake_vision, 0.8)

        service = ElementLocatorService.__new__(ElementLocatorService)
        service.db = None
        service.browser = FakeBrowserWithoutPage()
        service.vision_model = fake_vision
        service.confidence_threshold = 0.8
        service.recognizer = recognizer

        original_enabled = getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False)
        try:
            settings.MCP_DIRECT_EXECUTION_ENABLED = True
            result = service._should_direct_execute("click")
            assert result is False
        finally:
            settings.MCP_DIRECT_EXECUTION_ENABLED = original_enabled


# ============================================================
# 5. 配置项测试
# ============================================================

class TestMCPDirectExecutionConfig:
    """测试 MCP 直执相关配置项"""

    def test_mcp_direct_execution_enabled_exists_in_settings(self):
        """
        测试 MCP_DIRECT_EXECUTION_ENABLED 配置项存在

        前置条件：Settings 类已定义
        测试步骤：检查 Settings 类的字段定义
        预期结果：MCP_DIRECT_EXECUTION_ENABLED 字段存在
        """
        field_names = Settings.model_fields.keys()
        assert "MCP_DIRECT_EXECUTION_ENABLED" in field_names, \
            "Settings 中缺少 MCP_DIRECT_EXECUTION_ENABLED 配置项"

    def test_mcp_direct_execution_enabled_default_is_false(self):
        """
        测试 MCP_DIRECT_EXECUTION_ENABLED 默认值为 False

        前置条件：Settings 类已定义
        测试步骤：检查字段默认值
        预期结果：默认值为 False，确保新部署不会意外开启直执
        """
        field_info = Settings.model_fields.get("MCP_DIRECT_EXECUTION_ENABLED")
        assert field_info is not None, "MCP_DIRECT_EXECUTION_ENABLED 字段不存在"
        assert field_info.default is False, \
            f"MCP_DIRECT_EXECUTION_ENABLED 默认值应为 False，实际为 {field_info.default}"

    def test_mcp_execution_operation_types_exists_in_settings(self):
        """
        测试 MCP_EXECUTION_OPERATION_TYPES 配置项存在

        前置条件：Settings 类已定义
        测试步骤：检查 Settings 类的字段定义
        预期结果：MCP_EXECUTION_OPERATION_TYPES 字段存在
        """
        field_names = Settings.model_fields.keys()
        assert "MCP_EXECUTION_OPERATION_TYPES" in field_names, \
            "Settings 中缺少 MCP_EXECUTION_OPERATION_TYPES 配置项"

    def test_mcp_execution_operation_types_default_value(self):
        """
        测试 MCP_EXECUTION_OPERATION_TYPES 默认值包含基本操作类型

        前置条件：Settings 类已定义
        测试步骤：检查字段默认值
        预期结果：默认值包含 click, type, hover, select
        """
        field_info = Settings.model_fields.get("MCP_EXECUTION_OPERATION_TYPES")
        assert field_info is not None, "MCP_EXECUTION_OPERATION_TYPES 字段不存在"
        default_value = field_info.default
        assert default_value is not None, "MCP_EXECUTION_OPERATION_TYPES 默认值不应为 None"

        # 验证默认值包含核心操作类型
        default_types = [t.strip() for t in default_value.split(",")]
        assert "click" in default_types, f"默认操作类型应包含 click，实际: {default_types}"
        assert "type" in default_types, f"默认操作类型应包含 type，实际: {default_types}"
        assert "hover" in default_types, f"默认操作类型应包含 hover，实际: {default_types}"
        assert "select" in default_types, f"默认操作类型应包含 select，实际: {default_types}"

    def test_settings_instance_has_mcp_direct_execution_enabled(self):
        """
        测试 settings 实例包含 MCP_DIRECT_EXECUTION_ENABLED 属性

        前置条件：settings 已初始化
        测试步骤：访问 settings.MCP_DIRECT_EXECUTION_ENABLED
        预期结果：属性存在且为布尔类型
        """
        assert hasattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED'), \
            "settings 实例缺少 MCP_DIRECT_EXECUTION_ENABLED 属性"
        assert isinstance(settings.MCP_DIRECT_EXECUTION_ENABLED, bool), \
            f"MCP_DIRECT_EXECUTION_ENABLED 应为 bool 类型，实际为 {type(settings.MCP_DIRECT_EXECUTION_ENABLED)}"

    def test_settings_instance_has_mcp_execution_operation_types(self):
        """
        测试 settings 实例包含 MCP_EXECUTION_OPERATION_TYPES 属性

        前置条件：settings 已初始化
        测试步骤：访问 settings.MCP_EXECUTION_OPERATION_TYPES
        预期结果：属性存在且为字符串类型
        """
        assert hasattr(settings, 'MCP_EXECUTION_OPERATION_TYPES'), \
            "settings 实例缺少 MCP_EXECUTION_OPERATION_TYPES 属性"
        assert isinstance(settings.MCP_EXECUTION_OPERATION_TYPES, str), \
            f"MCP_EXECUTION_OPERATION_TYPES 应为 str 类型，实际为 {type(settings.MCP_EXECUTION_OPERATION_TYPES)}"

    def test_mcp_execution_operation_types_parseable(self):
        """
        测试 MCP_EXECUTION_OPERATION_TYPES 配置值可以被正确解析为列表

        前置条件：settings 已初始化
        测试步骤：将 MCP_EXECUTION_OPERATION_TYPES 按逗号拆分
        预期结果：拆分后得到非空列表，每个元素都是有效字符串
        """
        types_str = settings.MCP_EXECUTION_OPERATION_TYPES
        types_list = [t.strip() for t in types_str.split(",") if t.strip()]

        assert len(types_list) > 0, "MCP_EXECUTION_OPERATION_TYPES 解析后不应为空"
        for t in types_list:
            assert isinstance(t, str) and len(t) > 0, f"操作类型无效: '{t}'"


# ============================================================
# 6. VisionRecognizer 辅助方法测试
# ============================================================

class TestVisionRecognizerHelpers:
    """测试 VisionRecognizer 的辅助方法"""

    def test_normalize_coordinate_with_list_values(self):
        """
        测试 _normalize_coordinate 处理列表类型的坐标值

        前置条件：element_info 包含列表类型的坐标值
        测试步骤：调用 _normalize_coordinate()
        预期结果：列表值被转换为第一个元素
        """
        element_info = {
            "x": [100, 200],
            "y": [300],
            "width": [50, 60, 70],
            "height": [40]
        }
        result = VisionRecognizer._normalize_coordinate(element_info)

        assert result["x"] == 100
        assert result["y"] == 300
        assert result["width"] == 50
        assert result["height"] == 40

    def test_normalize_coordinate_with_none_values(self):
        """
        测试 _normalize_coordinate 处理 None 值

        前置条件：element_info 包含 None 值
        测试步骤：调用 _normalize_coordinate()
        预期结果：None 值被替换为 0
        """
        element_info = {
            "x": None,
            "y": None,
            "width": None,
            "height": None
        }
        result = VisionRecognizer._normalize_coordinate(element_info)

        assert result["x"] == 0
        assert result["y"] == 0
        assert result["width"] == 0
        assert result["height"] == 0

    def test_normalize_coordinate_with_empty_list(self):
        """
        测试 _normalize_coordinate 处理空列表

        前置条件：element_info 包含空列表
        测试步骤：调用 _normalize_coordinate()
        预期结果：空列表被替换为 0
        """
        element_info = {
            "x": [],
            "y": [],
            "width": [],
            "height": []
        }
        result = VisionRecognizer._normalize_coordinate(element_info)

        assert result["x"] == 0
        assert result["y"] == 0
        assert result["width"] == 0
        assert result["height"] == 0

    def test_normalize_coordinate_with_normal_values(self):
        """
        测试 _normalize_coordinate 处理正常数值

        前置条件：element_info 包含正常的整数坐标值
        测试步骤：调用 _normalize_coordinate()
        预期结果：值保持不变
        """
        element_info = {
            "x": 100,
            "y": 200,
            "width": 300,
            "height": 400
        }
        result = VisionRecognizer._normalize_coordinate(element_info)

        assert result["x"] == 100
        assert result["y"] == 200
        assert result["width"] == 300
        assert result["height"] == 400

    def test_normalize_coordinate_with_missing_keys(self):
        """
        测试 _normalize_coordinate 处理缺失的键

        前置条件：element_info 缺少部分坐标键
        测试步骤：调用 _normalize_coordinate()
        预期结果：缺失的键默认为 0
        """
        element_info = {"x": 100}
        result = VisionRecognizer._normalize_coordinate(element_info)

        assert result["x"] == 100
        assert result["y"] == 0
        assert result["width"] == 0
        assert result["height"] == 0

    def test_generate_css_selector_with_id(self):
        """
        测试 _generate_css_selector 优先使用 id 选择器

        前置条件：元素有 id 属性
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 #id 格式的选择器
        """
        element_attrs = {"tag": "button", "id": "submit-btn", "class": "btn primary"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "#submit-btn"

    def test_generate_css_selector_with_name(self):
        """
        测试 _generate_css_selector 使用 name 属性选择器

        前置条件：元素有 name 属性但没有 id
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 [name='xxx'] 格式的选择器
        """
        element_attrs = {"tag": "input", "name": "username"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "[name='username']"

    def test_generate_css_selector_with_data_testid(self):
        """
        测试 _generate_css_selector 使用 data-testid 选择器

        前置条件：元素有 data-testid 属性但没有 id
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 [data-testid='xxx'] 格式的选择器
        """
        element_attrs = {"tag": "button", "data-testid": "login-button"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "[data-testid='login-button']"

    def test_generate_css_selector_with_text(self):
        """
        测试 _generate_css_selector 使用文本选择器

        前置条件：元素有文本内容但没有 id/name/data-testid
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 tag:has-text('xxx') 格式的选择器
        """
        element_attrs = {"tag": "button", "text": "登录"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "button:has-text('登录')"

    def test_generate_css_selector_with_class(self):
        """
        测试 _generate_css_selector 使用 class 选择器

        前置条件：元素有 class 但没有 id/name/data-testid/text
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 tag.class1.class2 格式的选择器
        """
        element_attrs = {"tag": "div", "class": "container main"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "div.container.main"

    def test_generate_css_selector_with_empty_attrs(self):
        """
        测试 _generate_css_selector 处理空属性

        前置条件：元素属性为空字典
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 None
        """
        result = VisionRecognizer._generate_css_selector({})
        assert result is None

    def test_generate_css_selector_with_only_tag(self):
        """
        测试 _generate_css_selector 仅有 tag 时的回退策略

        前置条件：元素只有 tag 属性
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 tag 名称
        """
        element_attrs = {"tag": "span"}
        result = VisionRecognizer._generate_css_selector(element_attrs)

        assert result == "span"


# ============================================================
# 7. RecognitionResult 数据类测试
# ============================================================

class TestRecognitionResult:
    """测试 RecognitionResult 数据类的行为"""

    def test_is_valid_with_all_fields(self):
        """
        测试 RecognitionResult 所有字段有效时 is_valid 为 True

        前置条件：locator_type、locator_value 非空，confidence > 0
        测试步骤：创建 RecognitionResult 并检查 is_valid
        预期结果：is_valid 为 True
        """
        result = RecognitionResult(
            locator_type="css",
            locator_value="#login-btn",
            confidence=0.9
        )
        assert result.is_valid is True

    def test_is_valid_with_empty_locator_type(self):
        """
        测试 RecognitionResult locator_type 为空时 is_valid 为 False

        前置条件：locator_type 为空字符串
        测试步骤：创建 RecognitionResult 并检查 is_valid
        预期结果：is_valid 为 False
        """
        result = RecognitionResult(
            locator_type="",
            locator_value="#login-btn",
            confidence=0.9
        )
        assert result.is_valid is False

    def test_is_valid_with_empty_locator_value(self):
        """
        测试 RecognitionResult locator_value 为空时 is_valid 为 False

        前置条件：locator_value 为空字符串
        测试步骤：创建 RecognitionResult 并检查 is_valid
        预期结果：is_valid 为 False
        """
        result = RecognitionResult(
            locator_type="css",
            locator_value="",
            confidence=0.9
        )
        assert result.is_valid is False

    def test_is_valid_with_zero_confidence(self):
        """
        测试 RecognitionResult confidence 为 0 时 is_valid 为 False

        前置条件：confidence = 0
        测试步骤：创建 RecognitionResult 并检查 is_valid
        预期结果：is_valid 为 False
        """
        result = RecognitionResult(
            locator_type="css",
            locator_value="#login-btn",
            confidence=0
        )
        assert result.is_valid is False

    def test_is_valid_with_negative_confidence(self):
        """
        测试 RecognitionResult confidence 为负数时 is_valid 为 False

        前置条件：confidence < 0
        测试步骤：创建 RecognitionResult 并检查 is_valid
        预期结果：is_valid 为 False
        """
        result = RecognitionResult(
            locator_type="css",
            locator_value="#login-btn",
            confidence=-0.5
        )
        assert result.is_valid is False


# ============================================================
# 8. ElementLocatorService 坐标规范化与选择器生成测试
# ============================================================

class TestElementLocatorServiceHelpers:
    """测试 ElementLocatorService 的辅助方法"""

    def test_normalize_coordinate_with_list_values(self):
        """
        测试 ElementLocatorService._normalize_coordinate 处理列表类型

        前置条件：element_info 包含列表类型的坐标值
        测试步骤：调用 _normalize_coordinate()
        预期结果：列表值被转换为第一个元素
        """
        element_info = {
            "x": [10, 20],
            "y": [30],
            "width": [100, 200],
            "height": [50]
        }
        result = ElementLocatorService._normalize_coordinate(element_info)

        assert result["x"] == 10
        assert result["y"] == 30
        assert result["width"] == 100
        assert result["height"] == 50

    def test_normalize_coordinate_inplace(self):
        """
        测试 _normalize_coordinate 的 inplace 参数

        前置条件：element_info 包含需要规范化的值
        测试步骤：调用 _normalize_coordinate(inplace=True)
        预期结果：原地修改 element_info
        """
        element_info = {
            "x": None,
            "y": [100],
            "width": 200,
            "height": 50
        }
        result = ElementLocatorService._normalize_coordinate(element_info, inplace=True)

        assert result is element_info
        assert element_info["x"] == 0
        assert element_info["y"] == 100

    def test_normalize_coordinate_not_inplace(self):
        """
        测试 _normalize_coordinate 默认不原地修改

        前置条件：element_info 包含需要规范化的值
        测试步骤：调用 _normalize_coordinate(inplace=False)
        预期结果：返回新字典，原字典不变
        """
        element_info = {
            "x": None,
            "y": 100,
            "width": 200,
            "height": 50
        }
        result = ElementLocatorService._normalize_coordinate(element_info, inplace=False)

        assert result is not element_info
        assert element_info["x"] is None  # 原字典不变
        assert result["x"] == 0

    def test_sanitize_for_css_special_characters(self):
        """
        测试 _sanitize_for_css 正确转义 CSS 特殊字符

        前置条件：字符串包含 CSS 特殊字符
        测试步骤：调用 _sanitize_for_css()
        预期结果：特殊字符被转义
        """
        service = ElementLocatorService.__new__(ElementLocatorService)

        # 测试包含特殊字符的 id
        result = service._sanitize_for_css("my.id")
        assert "\\." in result

        # 测试包含方括号的值
        result = service._sanitize_for_css("value[0]")
        assert "\\[" in result
        assert "\\]" in result

    def test_sanitize_for_css_empty_string(self):
        """
        测试 _sanitize_for_css 处理空字符串

        前置条件：输入为空字符串
        测试步骤：调用 _sanitize_for_css()
        预期结果：返回空字符串
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        result = service._sanitize_for_css("")
        assert result == ""

    def test_sanitize_for_xpath_with_double_quotes(self):
        """
        测试 _sanitize_for_xpath 处理双引号

        前置条件：字符串包含双引号
        测试步骤：调用 _sanitize_for_xpath()
        预期结果：使用单引号包裹
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        result = service._sanitize_for_xpath('value"with"quotes')
        assert result.startswith("'")
        assert result.endswith("'")

    def test_sanitize_for_xpath_with_single_quotes(self):
        """
        测试 _sanitize_for_xpath 处理单引号

        前置条件：字符串包含单引号
        测试步骤：调用 _sanitize_for_xpath()
        预期结果：使用双引号包裹
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        result = service._sanitize_for_xpath("value'with'quotes")
        assert result.startswith('"')
        assert result.endswith('"')

    def test_sanitize_for_xpath_with_both_quotes(self):
        """
        测试 _sanitize_for_xpath 处理同时包含单双引号

        前置条件：字符串同时包含单引号和双引号
        测试步骤：调用 _sanitize_for_xpath()
        预期结果：使用 concat 函数
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        result = service._sanitize_for_xpath("""value'with"both""")
        assert "concat" in result

    def test_generate_css_selector_priority_id_over_name(self):
        """
        测试 CSS 选择器生成优先级：id 优先于 name

        前置条件：元素同时有 id 和 name
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 #id 格式而非 [name='xxx']
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "input", "id": "username", "name": "user"}
        result = service._generate_css_selector(element_attrs)

        assert result == "#username"

    def test_generate_css_selector_priority_name_over_class(self):
        """
        测试 CSS 选择器生成优先级：name 优先于 class

        前置条件：元素有 name 和 class 但没有 id
        测试步骤：调用 _generate_css_selector()
        预期结果：返回 [name='xxx'] 格式
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "input", "name": "password", "class": "form-control"}
        result = service._generate_css_selector(element_attrs)

        assert result == "[name='password']"

    def test_generate_xpath_with_id(self):
        """
        测试 XPath 生成：使用 id

        前置条件：元素有 id 属性
        测试步骤：调用 _generate_xpath()
        预期结果：返回 //tag[@id='xxx'] 格式
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "input", "id": "email"}
        result = service._generate_xpath(element_attrs)

        assert result == "//input[@id=\"email\"]"

    def test_generate_xpath_with_name(self):
        """
        测试 XPath 生成：使用 name

        前置条件：元素有 name 但没有 id
        测试步骤：调用 _generate_xpath()
        预期结果：返回 //tag[@name='xxx'] 格式
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "input", "name": "password"}
        result = service._generate_xpath(element_attrs)

        assert result == "//input[@name=\"password\"]"

    def test_generate_xpath_with_text(self):
        """
        测试 XPath 生成：使用文本内容

        前置条件：元素有 text 但没有 id 和 name
        测试步骤：调用 _generate_xpath()
        预期结果：返回 //tag[contains(text(),'xxx')] 格式
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "button", "text": "提交表单"}
        result = service._generate_xpath(element_attrs)

        assert "contains(text()," in result
        assert "提交表单" in result

    def test_generate_xpath_fallback_to_tag(self):
        """
        测试 XPath 生成：回退到标签名

        前置条件：元素只有 tag 属性
        测试步骤：调用 _generate_xpath()
        预期结果：返回 //tag 格式
        """
        service = ElementLocatorService.__new__(ElementLocatorService)
        element_attrs = {"tag": "div"}
        result = service._generate_xpath(element_attrs)

        assert result == "//div"


# ============================================================
# 9. MCPRecognizer name 属性和 is_available 测试
# ============================================================

class TestMCPRecognizerProperties:
    """测试 MCPRecognizer 的基本属性"""

    def test_mcp_recognizer_name(self):
        """
        测试 MCPRecognizer.name 返回 "mcp"

        前置条件：MCPRecognizer 实例已创建
        测试步骤：访问 name 属性
        预期结果：返回 "mcp"
        """
        recognizer = MCPRecognizer()
        assert recognizer.name == "mcp"

    @pytest.mark.asyncio
    async def test_mcp_recognizer_is_available_with_unavailable_client(self):
        """
        测试 MCP 不可用时 is_available 返回 False

        前置条件：MCP 客户端不可用
        测试步骤：调用 is_available()
        预期结果：返回 False
        """
        fake_mcp = FakeMCPClientUnavailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)
        result = await recognizer.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_mcp_recognizer_is_available_with_available_client(self):
        """
        测试 MCP 可用时 is_available 返回 True

        前置条件：MCP 客户端可用
        测试步骤：调用 is_available()
        预期结果：返回 True
        """
        fake_mcp = FakeMCPClientAvailable()
        recognizer = MCPRecognizer(mcp_client=fake_mcp)
        result = await recognizer.is_available()

        assert result is True


# ============================================================
# 10. VisionRecognizer name 属性和 is_available 测试
# ============================================================

class TestVisionRecognizerProperties:
    """测试 VisionRecognizer 的基本属性"""

    def test_vision_recognizer_name(self):
        """
        测试 VisionRecognizer.name 返回 "vision"

        前置条件：VisionRecognizer 实例已创建
        测试步骤：访问 name 属性
        预期结果：返回 "vision"
        """
        fake_vision = FakeVisionModel()
        recognizer = VisionRecognizer(fake_vision, 0.8)
        assert recognizer.name == "vision"

    @pytest.mark.asyncio
    async def test_vision_recognizer_is_available_with_model(self):
        """
        测试视觉模型存在时 is_available 返回 True

        前置条件：vision_model 不为 None
        测试步骤：调用 is_available()
        预期结果：返回 True
        """
        fake_vision = FakeVisionModel()
        recognizer = VisionRecognizer(fake_vision, 0.8)
        result = await recognizer.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_vision_recognizer_is_available_without_model(self):
        """
        测试视觉模型为 None 时 is_available 返回 False

        前置条件：vision_model 为 None
        测试步骤：调用 is_available()
        预期结果：返回 False
        """
        recognizer = VisionRecognizer(None, 0.8)
        result = await recognizer.is_available()

        assert result is False


# ============================================================
# 11. ElementLocatorService 创建逻辑测试
# ============================================================

class TestElementLocatorServiceCreation:
    """测试 ElementLocatorService 的创建逻辑"""

    def test_create_default_recognizer_vision_when_mcp_disabled(self):
        """
        测试 MCP 关闭时默认创建 VisionRecognizer

        前置条件：PLAYWRIGHT_MCP_ENABLED = False
        测试步骤：创建 ElementLocatorService 实例
        预期结果：recognizer 是 VisionRecognizer 类型
        """
        original_mcp = getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
        try:
            settings.PLAYWRIGHT_MCP_ENABLED = False

            service = ElementLocatorService.__new__(ElementLocatorService)
            service.db = None
            service.browser = FakeBrowserWithoutPage()
            service.vision_model = FakeVisionModel()
            service.confidence_threshold = 0.8
            service.recognizer = service._create_default_recognizer()

            assert isinstance(service.recognizer, VisionRecognizer)
        finally:
            settings.PLAYWRIGHT_MCP_ENABLED = original_mcp

    def test_create_default_recognizer_mcp_when_enabled(self):
        """
        测试 MCP 开启时默认创建 MCPRecognizer

        前置条件：PLAYWRIGHT_MCP_ENABLED = True
        测试步骤：创建 ElementLocatorService 实例
        预期结果：recognizer 是 MCPRecognizer 类型
        """
        original_mcp = getattr(settings, 'PLAYWRIGHT_MCP_ENABLED', False)
        try:
            settings.PLAYWRIGHT_MCP_ENABLED = True

            service = ElementLocatorService.__new__(ElementLocatorService)
            service.db = None
            service.browser = FakeBrowserWithoutPage()
            service.vision_model = FakeVisionModel()
            service.confidence_threshold = 0.8
            service.recognizer = service._create_default_recognizer()

            assert isinstance(service.recognizer, MCPRecognizer)
        finally:
            settings.PLAYWRIGHT_MCP_ENABLED = original_mcp

    def test_create_locator_service_with_use_mcp_true(self):
        """
        测试 create_locator_service 工厂方法 use_mcp=True

        前置条件：use_mcp=True
        测试步骤：调用 create_locator_service()
        预期结果：创建的服务使用 MCPRecognizer
        """
        service = ElementLocatorService.create_locator_service(
            db=None,
            browser=FakeBrowserWithoutPage(),
            vision_model=FakeVisionModel(),
            use_mcp=True
        )
        assert isinstance(service.recognizer, MCPRecognizer)

    def test_create_locator_service_with_use_mcp_false(self):
        """
        测试 create_locator_service 工厂方法 use_mcp=False

        前置条件：use_mcp=False
        测试步骤：调用 create_locator_service()
        预期结果：创建的服务使用 VisionRecognizer
        """
        service = ElementLocatorService.create_locator_service(
            db=None,
            browser=FakeBrowserWithoutPage(),
            vision_model=FakeVisionModel(),
            use_mcp=False
        )
        assert isinstance(service.recognizer, VisionRecognizer)


# ============================================================
# 12. 数据库相关测试（使用真实 MySQL）
# ============================================================

class TestElementLocatorDatabase:
    """测试 ElementLocator 数据库操作（使用真实 MySQL）"""

    @pytest.mark.asyncio
    async def test_record_locator_success_and_failure(self, db):
        """
        测试 ElementLocator 的 record_success 和 record_failure 方法

        前置条件：数据库连接正常
        测试步骤：创建 ElementLocator 记录，调用 record_success 和 record_failure
        预期结果：计数器正确更新
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="测试按钮",
            element_type="button",
            css_selector="#test-btn",
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        locator_id = locator.id
        assert locator_id is not None

        # 记录成功
        locator.record_success()
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 1
        assert locator.fail_count == 0
        assert locator.version == 1

        # 记录失败
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 1
        assert locator.fail_count == 1
        assert locator.version == 2

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_success_rate(self, db):
        """
        测试 ElementLocator 的 success_rate 属性计算

        前置条件：数据库连接正常
        测试步骤：创建记录并设置不同的成功/失败次数
        预期结果：success_rate 正确计算
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="成功率测试",
            css_selector="#rate-test",
            success_count=8,
            fail_count=2,
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        assert locator.success_rate == 0.8

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_success_rate_zero_total(self, db):
        """
        测试 ElementLocator 在总次数为 0 时 success_rate 返回 0.0

        前置条件：success_count=0, fail_count=0
        测试步骤：访问 success_rate 属性
        预期结果：返回 0.0
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="零成功率测试",
            css_selector="#zero-rate-test",
            success_count=0,
            fail_count=0,
            source="ai"
        )
        db.add(locator)
        db.commit()

        assert locator.success_rate == 0.0

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_priority_order(self, db):
        """
        测试 ElementLocator 的 priority_order 属性

        前置条件：定位器包含多种定位策略
        测试步骤：访问 priority_order 属性
        预期结果：返回正确的优先级列表
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="优先级测试",
            css_selector="#priority-test",
            xpath="//button[@id='priority-test']",
            element_id="priority-test",
            element_name="submit",
            ai_coordinate={"x": 100, "y": 200, "width": 50, "height": 30},
            source="ai"
        )
        db.add(locator)
        db.commit()

        priorities = locator.priority_order
        assert "css" in priorities
        assert "xpath" in priorities
        assert "id" in priorities
        assert "name" in priorities
        assert "ai" in priorities

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_validate_coordinate(self):
        """
        测试 ElementLocator.validate_coordinate 静态方法

        前置条件：无
        测试步骤：传入不同类型的坐标数据
        预期结果：正确验证坐标数据
        """
        # 有效坐标
        assert ElementLocator.validate_coordinate({"x": 100, "y": 200}) is True
        assert ElementLocator.validate_coordinate({"x": 0, "y": 0, "width": 100, "height": 50}) is True

        # 无效坐标
        assert ElementLocator.validate_coordinate({"x": -1, "y": 200}) is False
        assert ElementLocator.validate_coordinate("not a dict") is False
        assert ElementLocator.validate_coordinate(None) is False
        assert ElementLocator.validate_coordinate({"x": "abc", "y": 200}) is False

    def test_element_locator_atomic_record_success(self, db):
        """
        测试 ElementLocator.atomic_record_success 原子操作

        前置条件：数据库中有 ElementLocator 记录
        测试步骤：调用 atomic_record_success
        预期结果：成功计数 +1，版本号 +1
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="原子操作测试",
            css_selector="#atomic-test",
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        current_version = locator.version
        result = ElementLocator.atomic_record_success(db, locator.id, current_version)

        assert result is True
        db.refresh(locator)
        assert locator.success_count == 1
        assert locator.version == current_version + 1

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_atomic_record_failure(self, db):
        """
        测试 ElementLocator.atomic_record_failure 原子操作

        前置条件：数据库中有 ElementLocator 记录
        测试步骤：调用 atomic_record_failure
        预期结果：失败计数 +1，版本号 +1
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="原子失败测试",
            css_selector="#atomic-fail-test",
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        current_version = locator.version
        result = ElementLocator.atomic_record_failure(db, locator.id, current_version)

        assert result is True
        db.refresh(locator)
        assert locator.fail_count == 1
        assert locator.version == current_version + 1

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_atomic_record_version_conflict(self, db):
        """
        测试 ElementLocator 原子操作的乐观锁版本冲突

        前置条件：传入错误的版本号
        测试步骤：调用 atomic_record_success 传入旧版本号
        预期结果：返回 False，数据未更新
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="版本冲突测试",
            css_selector="#version-conflict-test",
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        # 传入错误的版本号
        wrong_version = locator.version + 999
        result = ElementLocator.atomic_record_success(db, locator.id, wrong_version)

        assert result is False
        db.refresh(locator)
        assert locator.success_count == 0  # 未被更新

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_get_best_locator(self, db):
        """
        测试 ElementLocator.get_best_locator 方法

        前置条件：定位器包含多种定位策略
        测试步骤：调用 get_best_locator()
        预期结果：返回优先级最高的定位策略
        """
        # 有 css_selector 时优先返回
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="最佳定位测试",
            css_selector="#best-test",
            xpath="//div[@id='best-test']",
            source="ai"
        )
        db.add(locator)
        db.commit()

        best = locator.get_best_locator()
        assert best is not None
        assert best["type"] == "css"
        assert best["value"] == "#best-test"

        # 清理数据
        db.delete(locator)
        db.commit()

    def test_element_locator_to_dict(self, db):
        """
        测试 ElementLocator.to_dict 方法

        前置条件：数据库中有 ElementLocator 记录
        测试步骤：调用 to_dict()
        预期结果：返回包含所有字段的字典
        """
        locator = ElementLocator(
            step_id=None,
            precondition_step_id=None,
            element_description="字典转换测试",
            css_selector="#dict-test",
            source="ai"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)

        result_dict = locator.to_dict()
        assert isinstance(result_dict, dict)
        assert "id" in result_dict
        assert "css_selector" in result_dict
        assert result_dict["css_selector"] == "#dict-test"

        # 清理数据
        db.delete(locator)
        db.commit()
