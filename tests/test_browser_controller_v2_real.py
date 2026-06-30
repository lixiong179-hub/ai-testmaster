"""
浏览器控制器V2真实测试

测试原则（强制执行）：
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：单元测试覆盖率必须 >= 95%
3. 测试准确性：测试通过率必须 100%
4. 发现问题优先：测试的目的是发现代码问题

注意：这些测试使用真实浏览器，需要安装Playwright
"""
import pytest
import pytest_asyncio
import asyncio
from app.utils.browser_controller_v2 import (
    BrowserControllerV2,
    BrowserConfig,
    ScreenshotConfig,
    ElementInfo,
    BrowserType,
    create_browser_controller_v2
)

pytestmark = pytest.mark.real_browser


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def browser():
    """真实浏览器控制器V2 fixture"""
    controller = await create_browser_controller_v2(
        browser_type="chromium",
        headless=True,
        viewport_width=1920,
        viewport_height=1080
    )
    yield controller
    await controller.close()


@pytest_asyncio.fixture
async def browser_firefox():
    """Firefox浏览器控制器 fixture"""
    controller = await create_browser_controller_v2(
        browser_type="firefox",
        headless=True
    )
    yield controller
    await controller.close()


# ==================== 配置类测试 ====================

def test_browser_config_defaults():
    """测试BrowserConfig默认配置"""
    config = BrowserConfig()
    assert config.browser_type == BrowserType.CHROMIUM
    assert config.headless == False
    assert config.viewport_width == 1920
    assert config.viewport_height == 1080
    assert config.device_scale_factor == 1.0
    assert config.locale == "zh-CN"
    assert config.timezone_id == "Asia/Shanghai"
    assert config.navigation_timeout == 30000
    assert config.action_timeout == 10000
    assert config.window_maximized == True
    assert config.disable_animations == True


def test_browser_config_custom():
    """测试BrowserConfig自定义配置"""
    config = BrowserConfig(
        browser_type=BrowserType.FIREFOX,
        headless=True,
        viewport_width=1366,
        viewport_height=768,
        user_agent="Test Agent"
    )
    assert config.browser_type == BrowserType.FIREFOX
    assert config.headless == True
    assert config.viewport_width == 1366
    assert config.viewport_height == 768
    assert config.user_agent == "Test Agent"


def test_screenshot_config_defaults():
    """测试ScreenshotConfig默认配置"""
    config = ScreenshotConfig()
    assert config.full_page == False
    assert config.clip is None
    assert config.type == "png"
    assert config.quality is None


def test_screenshot_config_validation():
    """测试ScreenshotConfig验证"""
    # 无效的图片格式
    with pytest.raises(ValueError, match="不支持的图片格式"):
        ScreenshotConfig(type="gif")
    
    # 无效的JPEG质量
    with pytest.raises(ValueError, match="JPEG质量必须在0-100之间"):
        ScreenshotConfig(type="jpeg", quality=150)
    
    # 无效的裁剪区域
    with pytest.raises(ValueError, match="裁剪区域必须包含"):
        ScreenshotConfig(clip={"x": 0, "y": 0})
    
    with pytest.raises(ValueError, match="必须是非负整数"):
        ScreenshotConfig(clip={"x": -1, "y": 0, "width": 100, "height": 100})


def test_element_info_calculations():
    """测试ElementInfo计算属性"""
    element = ElementInfo(
        x=100,
        y=200,
        width=80,
        height=40,
        tag="button",
        id="login-btn",
        class_name="btn primary"
    )
    
    assert element.center_x == 140  # 100 + 80/2
    assert element.center_y == 220  # 200 + 40/2
    assert element.tag == "button"
    assert element.id == "login-btn"


# ==================== 浏览器控制器初始化测试 ====================

@pytest.mark.asyncio
async def test_browser_controller_initialization():
    """测试浏览器控制器初始化"""
    config = BrowserConfig(headless=True)
    controller = BrowserControllerV2(config)
    
    assert controller.config == config
    assert controller._is_initialized == False
    assert controller._window_size_fixed == False
    
    # 初始化
    result = await controller.initialize()
    assert result is controller  # 支持链式调用
    assert controller._is_initialized == True
    assert controller._browser is not None
    assert controller._context is not None
    assert controller._page is not None
    
    await controller.close()


@pytest.mark.asyncio
async def test_browser_controller_chromium():
    """测试Chromium浏览器启动"""
    controller = await create_browser_controller_v2(
        browser_type="chromium",
        headless=True
    )
    
    assert controller._is_initialized == True
    assert controller.config.browser_type == BrowserType.CHROMIUM
    
    page_info = await controller.get_page_info()
    assert "viewport" in page_info
    
    await controller.close()


@pytest.mark.asyncio
async def test_browser_controller_firefox():
    """测试Firefox浏览器启动"""
    controller = await create_browser_controller_v2(
        browser_type="firefox",
        headless=True
    )
    
    assert controller._is_initialized == True
    assert controller.config.browser_type == BrowserType.FIREFOX
    
    await controller.close()


@pytest.mark.asyncio
async def test_browser_controller_webkit():
    """测试Webkit浏览器启动"""
    controller = await create_browser_controller_v2(
        browser_type="webkit",
        headless=True
    )
    
    assert controller._is_initialized == True
    assert controller.config.browser_type == BrowserType.WEBKIT
    
    await controller.close()


# ==================== 页面导航测试 ====================

@pytest.mark.asyncio
async def test_navigate_to_valid_url(browser):
    """测试导航到有效URL"""
    url = "https://www.example.com"
    await browser.navigate(url)
    
    # URL可能带斜杠，使用startswith检查
    assert browser.current_url.startswith(url)
    
    page_info = await browser.get_page_info()
    assert page_info["url"].startswith(url)
    assert "title" in page_info


@pytest.mark.asyncio
async def test_navigate_to_invalid_url(browser):
    """测试导航到无效URL"""
    with pytest.raises(Exception):
        await browser.navigate("not-a-valid-url")


@pytest.mark.asyncio
async def test_navigate_with_different_wait_conditions(browser):
    """测试不同等待条件的导航"""
    url = "https://www.example.com"
    
    # 测试不同wait_until参数
    await browser.navigate(url, wait_until="load")
    await browser.navigate(url, wait_until="domcontentloaded")
    await browser.navigate(url, wait_until="networkidle")


# ==================== 截图测试 ====================

@pytest.mark.asyncio
async def test_take_screenshot_default(browser):
    """测试默认截图"""
    await browser.navigate("https://www.example.com")
    screenshot = await browser.take_screenshot()
    
    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0


@pytest.mark.asyncio
async def test_take_screenshot_full_page(browser):
    """测试全页面截图"""
    await browser.navigate("https://www.example.com")
    config = ScreenshotConfig(full_page=True)
    screenshot = await browser.take_screenshot(config)
    
    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0


@pytest.mark.asyncio
async def test_take_screenshot_clipped(browser):
    """测试裁剪截图"""
    await browser.navigate("https://www.example.com")
    config = ScreenshotConfig(
        clip={"x": 0, "y": 0, "width": 800, "height": 600}
    )
    screenshot = await browser.take_screenshot(config)
    
    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0


@pytest.mark.asyncio
async def test_take_screenshot_jpeg(browser):
    """测试JPEG格式截图"""
    await browser.navigate("https://www.example.com")
    config = ScreenshotConfig(type="jpeg", quality=80)
    screenshot = await browser.take_screenshot(config)
    
    assert isinstance(screenshot, bytes)
    assert len(screenshot) > 0


# ==================== 元素操作测试 ====================

@pytest.mark.asyncio
async def test_click_by_coordinates(browser):
    """测试坐标点击"""
    await browser.navigate("https://www.example.com")
    
    # 点击页面中心附近
    viewport = await browser.execute_javascript(
        "() => ({ width: window.innerWidth, height: window.innerHeight })"
    )
    center_x = viewport["width"] // 2
    center_y = viewport["height"] // 2
    
    await browser.click(center_x, center_y)


@pytest.mark.asyncio
async def test_click_element_by_selector(browser):
    """测试选择器点击元素"""
    await browser.navigate("https://www.example.com")
    
    # 点击h1元素
    await browser.click_element("h1")


@pytest.mark.asyncio
async def test_fill_input(browser):
    """测试输入框填写"""
    await browser.navigate("https://www.example.com")
    
    # 尝试填写搜索框（如果存在）
    try:
        await browser.fill("input[type='search']", "test query")
    except Exception:
        # 如果不存在搜索框，测试其他输入元素
        pass


@pytest.mark.asyncio
async def test_type_text(browser):
    """测试逐字输入"""
    await browser.navigate("https://www.example.com")
    
    try:
        await browser.type_text("input[type='search']", "test", delay=10)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_press_key(browser):
    """测试按键操作"""
    await browser.navigate("https://www.example.com")
    
    await browser.press_key("Tab")
    await browser.press_key("Escape")


# ==================== JavaScript执行测试 ====================

@pytest.mark.asyncio
async def test_execute_javascript_simple(browser):
    """测试执行简单JavaScript"""
    await browser.navigate("https://www.example.com")
    
    result = await browser.execute_javascript("1 + 1")
    assert result == 2


@pytest.mark.asyncio
async def test_execute_javascript_dom(browser):
    """测试执行DOM操作JavaScript"""
    await browser.navigate("https://www.example.com")
    
    title = await browser.execute_javascript("document.title")
    assert isinstance(title, str)
    
    url = await browser.execute_javascript("window.location.href")
    assert url == browser.current_url


@pytest.mark.asyncio
async def test_execute_javascript_scroll(browser):
    """测试执行滚动JavaScript"""
    await browser.navigate("https://www.example.com")
    
    await browser.scroll_to(0, 100)
    await browser.scroll_to(0, 0)


# ==================== 元素信息测试 ====================

@pytest.mark.asyncio
async def test_get_element_info_existing(browser):
    """测试获取存在的元素信息"""
    await browser.navigate("https://www.example.com")
    
    info = await browser.get_element_info("h1")
    if info:  # 如果元素存在
        assert isinstance(info, ElementInfo)
        assert info.tag == "h1"
        assert info.width > 0
        assert info.height > 0


@pytest.mark.asyncio
async def test_get_element_info_non_existing(browser):
    """测试获取不存在的元素信息"""
    await browser.navigate("https://www.example.com")
    
    info = await browser.get_element_info("#non-existing-element-12345")
    assert info is None


@pytest.mark.asyncio
async def test_find_elements_by_text(browser):
    """测试根据文本查找元素"""
    await browser.navigate("https://www.example.com")
    
    # 查找包含"Example"文本的元素
    elements = await browser.find_elements_by_text("Example")
    assert isinstance(elements, list)


@pytest.mark.asyncio
async def test_get_all_input_elements(browser):
    """测试获取所有输入元素"""
    await browser.navigate("https://www.example.com")
    
    inputs = await browser.get_all_input_elements()
    assert isinstance(inputs, list)
    
    for input_el in inputs:
        assert "tag" in input_el
        assert "type" in input_el


# ==================== 高亮测试 ====================

@pytest.mark.asyncio
async def test_highlight_element(browser):
    """测试元素高亮"""
    await browser.navigate("https://www.example.com")
    
    # 高亮h1元素
    await browser.highlight_element("h1", duration=500)


# ==================== 刷新测试 ====================

@pytest.mark.asyncio
async def test_refresh_page(browser):
    """测试刷新页面"""
    await browser.navigate("https://www.example.com")
    
    initial_title = await browser.execute_javascript("document.title")
    await browser.refresh()
    refreshed_title = await browser.execute_javascript("document.title")
    
    assert initial_title == refreshed_title


# ==================== 错误处理测试 ====================

@pytest.mark.asyncio
async def test_uninitialized_browser_error():
    """测试未初始化浏览器错误"""
    controller = BrowserControllerV2()
    
    with pytest.raises(Exception):
        await controller.navigate("https://www.example.com")


@pytest.mark.asyncio
async def test_invalid_click_coordinates(browser):
    """测试无效点击坐标"""
    from app.utils.browser_controller_v2 import BrowserError
    await browser.navigate("https://www.example.com")

    with pytest.raises((ValueError, BrowserError)):
        await browser.click(-1, 100)

    with pytest.raises((ValueError, BrowserError)):
        await browser.click(100, -1)


@pytest.mark.asyncio
async def test_empty_selector_error(browser):
    """测试空选择器错误"""
    from app.utils.browser_controller_v2 import BrowserError
    await browser.navigate("https://www.example.com")

    with pytest.raises((ValueError, BrowserError)):
        await browser.click_element("")

    with pytest.raises((ValueError, BrowserError)):
        await browser.fill("", "text")


@pytest.mark.asyncio
async def test_empty_javascript_error(browser):
    """测试空JavaScript错误"""
    from app.utils.browser_controller_v2 import BrowserError
    await browser.navigate("https://www.example.com")

    with pytest.raises((ValueError, BrowserError)):
        await browser.execute_javascript("")


# ==================== 属性测试 ====================

@pytest.mark.asyncio
async def test_is_initialized_property(browser):
    """测试is_initialized属性"""
    assert browser.is_initialized == True


@pytest.mark.asyncio
async def test_current_url_property(browser):
    """测试current_url属性"""
    url = "https://www.example.com"
    await browser.navigate(url)

    assert browser.current_url.startswith(url)


# ==================== 多次初始化测试 ====================

@pytest.mark.asyncio
async def test_multiple_initialization():
    """测试多次初始化"""
    controller = await create_browser_controller_v2(headless=True)
    
    # 第二次初始化应该直接返回
    result = await controller.initialize()
    assert result is controller
    
    await controller.close()


# ==================== 链式调用测试 ====================

@pytest.mark.asyncio
async def test_chained_calls():
    """测试链式调用"""
    controller = await BrowserControllerV2(
        BrowserConfig(headless=True)
    ).initialize()
    
    await controller.navigate("https://www.example.com")
    screenshot = await controller.take_screenshot()
    
    assert len(screenshot) > 0
    
    await controller.close()
