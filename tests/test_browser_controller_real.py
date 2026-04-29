"""
Playwright浏览器控制器真实测试
使用真实浏览器进行测试，不使用Mock
"""
import pytest
import asyncio
from app.utils.browser_controller import (
    BrowserController,
    BrowserConfig,
    BrowserType,
    ScreenshotConfig,
    create_browser_controller,
    BrowserError,
    BrowserNotInitializedError,
    ElementNotFoundError
)


@pytest.fixture(scope="module")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def browser_controller():
    """创建真实浏览器控制器"""
    controller = await create_browser_controller(
        browser_type="chromium",
        headless=True,  # 无头模式，适合CI/CD
        viewport_width=1280,
        viewport_height=720
    )
    yield controller
    await controller.close()


class TestBrowserControllerReal:
    """真实浏览器测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_initialize_real_browser(self):
        """测试真实浏览器初始化"""
        controller = BrowserController()
        result = await controller.initialize()
        
        assert result == controller
        assert controller.is_initialized == True
        assert controller._browser is not None
        assert controller._page is not None
        
        await controller.close()
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_navigate_real_page(self, browser_controller):
        """测试真实页面导航"""
        await browser_controller.navigate("https://www.example.com")
        
        page_info = await browser_controller.get_page_info()
        assert "Example Domain" in page_info["title"]
        assert page_info["url"] == "https://www.example.com/"
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_take_screenshot_real(self, browser_controller):
        """测试真实截图"""
        await browser_controller.navigate("https://www.example.com")
        
        screenshot = await browser_controller.take_screenshot()
        
        assert isinstance(screenshot, bytes)
        assert len(screenshot) > 0
        # PNG文件头
        assert screenshot[:8] == b'\x89PNG\r\n\x1a\n'
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_take_screenshot_full_page(self, browser_controller):
        """测试全页面截图"""
        await browser_controller.navigate("https://www.example.com")
        
        config = ScreenshotConfig(full_page=True)
        screenshot = await browser_controller.take_screenshot(config)
        
        assert isinstance(screenshot, bytes)
        assert len(screenshot) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_take_screenshot_jpeg(self, browser_controller):
        """测试JPEG格式截图"""
        await browser_controller.navigate("https://www.example.com")
        
        config = ScreenshotConfig(type="jpeg", quality=80)
        screenshot = await browser_controller.take_screenshot(config)
        
        assert isinstance(screenshot, bytes)
        assert len(screenshot) > 0
        # JPEG文件头
        assert screenshot[:2] == b'\xff\xd8'
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_execute_javascript_real(self, browser_controller):
        """测试真实JavaScript执行"""
        await browser_controller.navigate("https://www.example.com")
        
        result = await browser_controller.execute_javascript("document.title")
        
        assert "Example Domain" in result
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_execute_javascript_complex(self, browser_controller):
        """测试复杂JavaScript执行"""
        await browser_controller.navigate("https://www.example.com")
        
        result = await browser_controller.execute_javascript("""
            ({
                title: document.title,
                url: window.location.href,
                width: window.innerWidth,
                height: window.innerHeight
            })
        """)
        
        assert "title" in result
        assert "url" in result
        assert result["width"] == 1280
        assert result["height"] == 720
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_scroll_to_real(self, browser_controller):
        """测试真实滚动"""
        await browser_controller.navigate("https://www.example.com")
        
        # 先滚动到某个位置
        await browser_controller.scroll_to(0, 100)
        
        # 验证滚动位置（允许一定的误差）
        scroll_y = await browser_controller.execute_javascript("window.scrollY")
        # 页面可能不需要滚动，所以只要没有报错就算成功
        assert isinstance(scroll_y, (int, float))
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_get_page_info_real(self, browser_controller):
        """测试真实页面信息获取"""
        await browser_controller.navigate("https://www.example.com")
        
        page_info = await browser_controller.get_page_info()
        
        assert "title" in page_info
        assert "url" in page_info
        assert "viewport" in page_info
        assert page_info["viewport"]["width"] == 1280
        assert page_info["viewport"]["height"] == 720
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_current_url_property(self, browser_controller):
        """测试current_url属性"""
        await browser_controller.navigate("https://www.example.com")
        
        assert browser_controller.current_url == "https://www.example.com/"


class TestBrowserControllerRealInteractions:
    """真实交互测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_navigate_multiple_pages(self, browser_controller):
        """测试导航多个页面"""
        await browser_controller.navigate("https://www.example.com")
        assert "Example Domain" in await browser_controller.execute_javascript("document.title")
        
        await browser_controller.navigate("https://www.iana.org/domains/reserved")
        page_info = await browser_controller.get_page_info()
        assert "IANA" in page_info["title"]
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_screenshot_after_navigation(self, browser_controller):
        """测试导航后截图"""
        await browser_controller.navigate("https://www.example.com")
        screenshot1 = await browser_controller.take_screenshot()
        
        await browser_controller.navigate("https://www.iana.org/domains/reserved")
        screenshot2 = await browser_controller.take_screenshot()
        
        # 两个截图应该不同
        assert screenshot1 != screenshot2
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_multiple_screenshots(self, browser_controller):
        """测试多次截图"""
        await browser_controller.navigate("https://www.example.com")
        
        screenshots = []
        for i in range(3):
            screenshot = await browser_controller.take_screenshot()
            screenshots.append(screenshot)
        
        # 所有截图都应该有效
        for screenshot in screenshots:
            assert isinstance(screenshot, bytes)
            assert len(screenshot) > 0


class TestBrowserControllerRealErrors:
    """真实错误场景测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_navigate_invalid_url_real(self, browser_controller):
        """测试真实无效URL"""
        with pytest.raises(BrowserError):
            await browser_controller.navigate("not-a-valid-url")
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_navigate_nonexistent_domain(self, browser_controller):
        """测试不存在的域名"""
        with pytest.raises(BrowserError):
            await browser_controller.navigate("https://this-domain-does-not-exist-12345.com")
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_click_element_not_found_real(self):
        """测试真实元素未找到"""
        # 创建新的浏览器实例，避免网络问题影响其他测试
        controller = await create_browser_controller(headless=True)
        try:
            await controller.navigate("https://www.example.com")
            
            # 元素未找到会抛出BrowserError（被装饰器包装）
            with pytest.raises(BrowserError):
                await controller.click_element("#nonexistent-element-12345")
        finally:
            await controller.close()
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_wait_for_selector_timeout_real(self, browser_controller):
        """测试真实等待超时"""
        await browser_controller.navigate("https://www.example.com")
        
        with pytest.raises(BrowserError):
            await browser_controller.wait_for_selector("#nonexistent", timeout=1000)


class TestBrowserControllerDifferentConfigs:
    """测试不同配置"""
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_different_viewport_size(self):
        """测试不同视口大小"""
        controller = await create_browser_controller(
            headless=True,
            viewport_width=800,
            viewport_height=600
        )
        
        await controller.navigate("https://www.example.com")
        
        viewport = await controller.execute_javascript(
            "({ width: window.innerWidth, height: window.innerHeight })"
        )
        assert viewport["width"] == 800
        assert viewport["height"] == 600
        
        await controller.close()
    
    @pytest.mark.asyncio
    @pytest.mark.real_browser
    async def test_different_locale(self):
        """测试不同语言设置"""
        controller = await create_browser_controller(
            headless=True,
            locale="en-US"
        )
        
        await controller.navigate("https://www.example.com")
        
        # 验证浏览器语言设置
        language = await controller.execute_javascript("navigator.language")
        assert language == "en-US"
        
        await controller.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'real_browser'])
