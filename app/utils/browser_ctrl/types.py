"""
浏览器控制器类型定义模块

定义浏览器控制器的异常体系、配置数据类和通用装饰器。
是browser_ctrl包的基础设施模块，被所有Mixin引用。

异常体系：
    - BrowserError: 浏览器操作基础异常
    - BrowserNotInitializedError: 浏览器未初始化
    - NavigationError: 导航失败
    - ElementNotFoundError: 元素未找到

配置数据类：
    - BrowserConfig: 浏览器启动配置（类型、视口、超时等）
    - ScreenshotConfig: 截图配置（格式、质量、全页）

装饰器：
    - require_initialized: 确保浏览器已初始化，否则抛出BrowserNotInitializedError
    - handle_browser_errors: 捕获Playwright异常，统一转换为BrowserError
"""
import functools
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum


class BrowserType(str, Enum):
    """浏览器类型枚举

    支持Playwright提供的三种浏览器引擎。
    继承str和Enum，可直接作为字符串使用。
    """
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


class BrowserError(Exception):
    """浏览器操作基础异常

    所有浏览器相关异常的基类，由handle_browser_errors装饰器自动抛出。
    """
    pass


class BrowserNotInitializedError(BrowserError):
    """浏览器未初始化异常

    在调用需要浏览器实例的方法前未调用initialize()时抛出。
    由require_initialized装饰器自动检测。
    """
    pass


class NavigationError(BrowserError):
    """页面导航异常

    页面跳转、刷新等导航操作失败时抛出。
    """
    pass


class ElementNotFoundError(BrowserError):
    """元素未找到异常

    通过选择器查找元素失败时抛出，通常是因为选择器错误或元素尚未加载。
    """
    pass


@dataclass
class BrowserConfig:
    """浏览器启动配置

    Attributes:
        headless: 是否无头模式运行，默认False
        browser_type: 浏览器引擎类型，默认Chromium
        viewport_width: 视口宽度（像素），默认1920
        viewport_height: 视口高度（像素），默认1080
        timeout: 默认操作超时时间（毫秒），默认30000
        slow_mo: 操作间延迟（毫秒），用于调试，默认0
        ignore_https_errors: 是否忽略HTTPS证书错误，默认True
        args: 传递给浏览器的额外启动参数
    """
    headless: bool = False
    browser_type: BrowserType = BrowserType.CHROMIUM
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000
    slow_mo: int = 0
    ignore_https_errors: bool = True
    # 默认启动参数：禁用自动化检测标记 + 禁用沙箱（Docker兼容）
    args: List[str] = field(default_factory=lambda: [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
    ])


@dataclass
class ScreenshotConfig:
    """截图配置

    Attributes:
        full_page: 是否截取完整页面（含滚动区域），默认False
        type: 图片格式（"png"或"jpeg"），默认png
        quality: JPEG质量（1-100），仅type="jpeg"时生效，默认None（使用Playwright默认值）
    """
    full_page: bool = False
    type: str = "png"
    quality: Optional[int] = None


def require_initialized(func: Callable) -> Callable:
    """浏览器初始化检查装饰器

    在方法执行前检查self._page是否存在，不存在则抛出BrowserNotInitializedError。
    所有需要操作页面的Mixin方法都应使用此装饰器。

    Args:
        func: 被装饰的异步方法

    Returns:
        Callable: 包装后的异步方法
    """
    @functools.wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not self._page:
            raise BrowserNotInitializedError("浏览器未初始化，请先调用 initialize()")
        return await func(self, *args, **kwargs)
    return wrapper


def handle_browser_errors(func: Callable) -> Callable:
    """浏览器异常统一处理装饰器

    捕获Playwright抛出的各类异常，统一转换为BrowserError。
    已有的BrowserError子类异常直接透传，不重复包装。

    Args:
        func: 被装饰的异步方法

    Returns:
        Callable: 包装后的异步方法
    """
    @functools.wraps(func)
    async def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except BrowserError:
            raise
        except Exception as e:
            from loguru import logger
            logger.error(f"浏览器操作失败 [{func.__name__}]: {str(e)}")
            raise BrowserError(f"浏览器操作失败: {str(e)}") from e
    return wrapper
