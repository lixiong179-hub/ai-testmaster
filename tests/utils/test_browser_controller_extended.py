import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.browser_controller_base import (
    BrowserType,
    BrowserError,
    BrowserNotInitializedError,
    NavigationError,
    ElementNotFoundError,
    BrowserConfig,
    ElementInfo,
    require_initialized,
    handle_browser_errors,
    BrowserControllerV2 as BaseBrowserControllerV2,
)
from app.utils.browser_controller_navigation import NavigationMixin, ScreenshotConfig
from app.utils.browser_controller_actions import ActionMixin
from app.utils.browser_controller_v2 import BrowserControllerV2, create_browser_controller_v2


class TestBrowserType:
    def test_values(self):
        assert BrowserType.CHROMIUM == "chromium"
        assert BrowserType.FIREFOX == "firefox"
        assert BrowserType.WEBKIT == "webkit"


class TestBrowserErrors:
    def test_browser_error(self):
        with pytest.raises(BrowserError):
            raise BrowserError("test")

    def test_browser_not_initialized_error(self):
        assert issubclass(BrowserNotInitializedError, BrowserError)

    def test_navigation_error(self):
        assert issubclass(NavigationError, BrowserError)

    def test_element_not_found_error(self):
        assert issubclass(ElementNotFoundError, BrowserError)


class TestBrowserConfig:
    def test_defaults(self):
        config = BrowserConfig()
        assert config.browser_type == BrowserType.CHROMIUM
        assert config.headless is False
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.locale == "zh-CN"

    def test_custom(self):
        config = BrowserConfig(
            browser_type=BrowserType.FIREFOX,
            headless=True,
            viewport_width=1280,
        )
        assert config.browser_type == BrowserType.FIREFOX
        assert config.headless is True


class TestElementInfo:
    def test_center_x(self):
        info = ElementInfo(x=100, y=200, width=50, height=60)
        assert info.center_x == 125.0

    def test_center_y(self):
        info = ElementInfo(x=100, y=200, width=50, height=60)
        assert info.center_y == 230.0

    def test_defaults(self):
        info = ElementInfo(x=0, y=0, width=100, height=100)
        assert info.tag == ""
        assert info.id == ""
        assert info.text == ""
        assert info.attributes == {}


class TestRequireInitialized:
    @pytest.mark.asyncio
    async def test_not_initialized(self):
        class MockController:
            _is_initialized = False

            @require_initialized
            async def test_method(self):
                return "success"

        ctrl = MockController()
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.test_method()

    @pytest.mark.asyncio
    async def test_initialized(self):
        class MockController:
            _is_initialized = True

            @require_initialized
            async def test_method(self):
                return "success"

        ctrl = MockController()
        result = await ctrl.test_method()
        assert result == "success"


class TestHandleBrowserErrors:
    @pytest.mark.asyncio
    async def test_browser_error_passthrough(self):
        class MockController:
            @handle_browser_errors
            async def test_method(self):
                raise BrowserError("test error")

        ctrl = MockController()
        with pytest.raises(BrowserError):
            await ctrl.test_method()

    @pytest.mark.asyncio
    async def test_timeout_error_wrapped(self):
        class MockController:
            @handle_browser_errors
            async def test_method(self):
                raise TimeoutError("timeout")

        ctrl = MockController()
        with pytest.raises(BrowserError, match="超时"):
            await ctrl.test_method()

    @pytest.mark.asyncio
    async def test_connection_error_wrapped(self):
        class MockController:
            @handle_browser_errors
            async def test_method(self):
                raise ConnectionError("connection lost")

        ctrl = MockController()
        with pytest.raises(BrowserError, match="连接错误"):
            await ctrl.test_method()

    @pytest.mark.asyncio
    async def test_generic_error_wrapped(self):
        class MockController:
            @handle_browser_errors
            async def test_method(self):
                raise RuntimeError("unexpected")

        ctrl = MockController()
        with pytest.raises(BrowserError, match="失败"):
            await ctrl.test_method()


class TestScreenshotConfig:
    def test_defaults(self):
        config = ScreenshotConfig()
        assert config.full_page is False
        assert config.type == "png"
        assert config.quality is None

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="不支持的图片格式"):
            ScreenshotConfig(type="gif")

    def test_invalid_quality(self):
        with pytest.raises(ValueError, match="JPEG质量"):
            ScreenshotConfig(type="jpeg", quality=200)

    def test_valid_jpeg(self):
        config = ScreenshotConfig(type="jpeg", quality=80)
        assert config.quality == 80

    def test_invalid_clip_missing_keys(self):
        with pytest.raises(ValueError, match="裁剪区域"):
            ScreenshotConfig(clip={"x": 0, "y": 0})

    def test_invalid_clip_negative_values(self):
        with pytest.raises(ValueError, match="必须是非负整数"):
            ScreenshotConfig(clip={"x": -1, "y": 0, "width": 100, "height": 100})

    def test_valid_clip(self):
        config = ScreenshotConfig(clip={"x": 0, "y": 0, "width": 100, "height": 100})
        assert config.clip is not None


class TestBaseBrowserControllerV2:
    def test_init_defaults(self):
        ctrl = BaseBrowserControllerV2()
        assert ctrl._is_initialized is False
        assert ctrl._page is None

    def test_is_initialized_property(self):
        ctrl = BaseBrowserControllerV2()
        assert ctrl.is_initialized is False

    def test_current_url_no_page(self):
        ctrl = BaseBrowserControllerV2()
        assert ctrl.current_url == ""

    @pytest.mark.asyncio
    async def test_close_not_initialized(self):
        ctrl = BaseBrowserControllerV2()
        result = await ctrl.close()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_with_video(self):
        ctrl = BaseBrowserControllerV2()
        ctrl.config = BrowserConfig(record_video=True)
        mock_page = MagicMock()
        mock_video = MagicMock()
        mock_video.path = AsyncMock(return_value="/tmp/video.webm")
        mock_page.video = mock_video
        ctrl._page = mock_page
        result = await ctrl.close()
        assert ctrl._is_initialized is False

    @pytest.mark.asyncio
    async def test_cleanup_resources(self):
        ctrl = BaseBrowserControllerV2()
        mock_page = MagicMock()
        mock_page.close = AsyncMock()
        ctrl._page = mock_page
        mock_context = MagicMock()
        mock_context.close = AsyncMock()
        ctrl._context = mock_context
        await ctrl._cleanup_resources()
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()


class TestNavigationMixin:
    @pytest.mark.asyncio
    async def test_navigate_invalid_url(self):
        class Ctrl(NavigationMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError):
            await ctrl.navigate("not_a_url")

    @pytest.mark.asyncio
    async def test_navigate_not_initialized(self):
        class Ctrl(NavigationMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.navigate("https://example.com")


class TestActionMixin:
    @pytest.mark.asyncio
    async def test_click_negative_coords(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="坐标必须非负"):
            await ctrl.click(-1, 0)

    @pytest.mark.asyncio
    async def test_hover_negative_coords(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="坐标必须非负"):
            await ctrl.hover(0, -1)

    @pytest.mark.asyncio
    async def test_click_element_empty_selector(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="CSS选择器不能为空"):
            await ctrl.click_element("")

    @pytest.mark.asyncio
    async def test_fill_empty_selector(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="CSS选择器不能为空"):
            await ctrl.fill("", "text")

    @pytest.mark.asyncio
    async def test_type_text_empty_selector(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="CSS选择器不能为空"):
            await ctrl.type_text("", "text")

    @pytest.mark.asyncio
    async def test_press_key_empty_key(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="按键名称不能为空"):
            await ctrl.press_key("")

    @pytest.mark.asyncio
    async def test_wait_for_selector_empty(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="CSS选择器不能为空"):
            await ctrl.wait_for_selector("")

    @pytest.mark.asyncio
    async def test_execute_javascript_empty(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        with pytest.raises(BrowserError, match="JavaScript代码不能为空"):
            await ctrl.execute_javascript("")

    @pytest.mark.asyncio
    async def test_get_element_info_empty_selector(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        result = await ctrl.get_element_info("")
        assert result is None

    @pytest.mark.asyncio
    async def test_highlight_element_empty_selector(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        ctrl._is_initialized = True
        result = await ctrl.highlight_element("")
        assert result is None

    @pytest.mark.asyncio
    async def test_not_initialized_actions(self):
        class Ctrl(ActionMixin, BaseBrowserControllerV2):
            pass
        ctrl = Ctrl()
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.click(10, 20)
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.hover(10, 20)
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.fill("#input", "text")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.type_text("#input", "text")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.press_key("Enter")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.wait_for_selector("#el")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.get_page_info()
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.execute_javascript("1+1")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.scroll_to(0, 0)
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.get_element_info("#el")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.highlight_element("#el")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.find_elements_by_text("text")
        with pytest.raises(BrowserNotInitializedError):
            await ctrl.get_all_input_elements()


class TestBrowserControllerV2:
    def test_inherits_mixins(self):
        assert issubclass(BrowserControllerV2, NavigationMixin)
        assert issubclass(BrowserControllerV2, ActionMixin)
        assert issubclass(BrowserControllerV2, BaseBrowserControllerV2)
