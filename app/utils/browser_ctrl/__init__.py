"""
浏览器控制器包

提供基于Playwright的浏览器自动化控制能力，采用Mixin组合模式将功能拆分为
四个独立的模块，按职责分离：

Mixin模块：
    - LifecycleMixin: 生命周期管理（初始化、关闭、资源清理）
    - NavigationMixin: 页面导航（跳转、刷新、前进/后退）
    - InteractionMixin: 元素交互（点击、输入、选择、等待）
    - MediaMixin: 媒体操作（截图、滚动、JS执行）

类型定义：
    - types.py: 异常类、配置数据类、装饰器（require_initialized/handle_browser_errors）

组合方式：
    BrowserController通过多重继承组合所有Mixin，对外提供统一的浏览器控制接口。
    每个Mixin通过self._page等属性访问Playwright页面对象，这些属性由
    BrowserController.__init__初始化。

使用示例：
    controller = create_browser_controller(headless=True)
    await controller.initialize()
    await controller.navigate("https://example.com")
    screenshot = await controller.take_screenshot()
    await controller.close()
"""
from typing import Optional, Dict, Any, List

from app.utils.browser_ctrl.types import (
    BrowserType, BrowserError, BrowserNotInitializedError,
    NavigationError, ElementNotFoundError, BrowserConfig, ScreenshotConfig,
    require_initialized, handle_browser_errors,
)
from app.utils.browser_ctrl.lifecycle_mixin import LifecycleMixin
from app.utils.browser_ctrl.navigation_mixin import NavigationMixin
from app.utils.browser_ctrl.interaction_mixin import InteractionMixin
from app.utils.browser_ctrl.media_mixin import MediaMixin


class BrowserController(
    LifecycleMixin,
    NavigationMixin,
    InteractionMixin,
    MediaMixin,
):
    """浏览器控制器主类

    通过Mixin多重继承组合生命周期、导航、交互、媒体四大能力。
    所有Mixin方法通过self._page访问Playwright页面对象，
    该属性在initialize()时创建，在close()时销毁。

    Attributes:
        _config: 浏览器配置（BrowserConfig实例）
        _playwright: Playwright实例
        _browser: Browser实例
        _context: BrowserContext实例
        _page: Page实例（所有Mixin的核心操作对象）
    """

    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self._config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None


def create_browser_controller(
    headless: bool = False,
    browser_type: BrowserType = BrowserType.CHROMIUM,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    timeout: int = 30000,
) -> BrowserController:
    """创建浏览器控制器的工厂函数

    提供更直观的参数接口，内部构建BrowserConfig后创建BrowserController实例。

    Args:
        headless: 是否无头模式运行，默认False（有界面）
        browser_type: 浏览器类型，默认Chromium
        viewport_width: 视口宽度，默认1920
        viewport_height: 视口高度，默认1080
        timeout: 默认超时时间（毫秒），默认30000

    Returns:
        BrowserController: 配置好的浏览器控制器实例（尚未初始化，需调用initialize()）
    """
    config = BrowserConfig(
        headless=headless,
        browser_type=browser_type,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        timeout=timeout,
    )
    return BrowserController(config=config)


__all__ = [
    'BrowserController',
    'BrowserType',
    'BrowserError',
    'BrowserNotInitializedError',
    'NavigationError',
    'ElementNotFoundError',
    'BrowserConfig',
    'ScreenshotConfig',
    'require_initialized',
    'handle_browser_errors',
    'create_browser_controller',
    'LifecycleMixin',
    'NavigationMixin',
    'InteractionMixin',
    'MediaMixin',
]
