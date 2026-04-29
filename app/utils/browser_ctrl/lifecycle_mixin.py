"""
浏览器生命周期管理Mixin

提供浏览器的初始化、关闭和资源清理功能。
是BrowserController最核心的Mixin，管理Playwright实例的完整生命周期。

核心方法：
    - initialize: 启动浏览器（创建Playwright → 启动Browser → 创建Context → 创建Page）
    - close: 关闭浏览器并释放所有资源
    - _cleanup_resources: 内部资源清理方法（安全关闭各层对象）

生命周期层次：
    Playwright → Browser → BrowserContext → Page
    初始化按此顺序创建，关闭按逆序销毁。

依赖：
    - playwright.async_api: Playwright异步API
    - app.utils.browser_ctrl.types: 配置类和异常类
"""
from typing import Optional
from loguru import logger

from app.utils.browser_ctrl.types import (
    BrowserConfig, BrowserType, BrowserNotInitializedError, handle_browser_errors,
)


class LifecycleMixin:
    """浏览器生命周期管理Mixin

    管理Playwright实例的完整生命周期，包括初始化、关闭和资源清理。
    初始化过程按 Playwright → Browser → Context → Page 的顺序创建，
    并支持从settings加载浏览器存储状态（如Cookie、localStorage）。
    """

    @handle_browser_errors
    async def initialize(self, headless: Optional[bool] = None) -> None:
        """初始化浏览器实例

        按顺序创建Playwright、Browser、Context和Page四层对象。
        支持通过参数覆盖配置中的headless设置。
        如果浏览器已初始化，跳过重复初始化。

        Args:
            headless: 是否无头模式，None时使用配置中的默认值

        Raises:
            BrowserNotInitializedError: Playwright未安装或初始化失败
        """
        if self._page:
            logger.warning("浏览器已初始化，跳过重复初始化")
            return

        effective_headless = headless if headless is not None else self._config.headless

        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

            browser_type_map = {
                BrowserType.CHROMIUM: self._playwright.chromium,
                BrowserType.FIREFOX: self._playwright.firefox,
                BrowserType.WEBKIT: self._playwright.webkit,
            }
            browser_launcher = browser_type_map.get(
                self._config.browser_type, self._playwright.chromium
            )

            launch_args = self._config.args or []
            self._browser = await browser_launcher.launch(
                headless=effective_headless,
                slow_mo=self._config.slow_mo,
                args=launch_args,
                ignore_https_errors=self._config.ignore_https_errors,
            )

            context_args = {
                "viewport": {
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                "ignore_https_errors": self._config.ignore_https_errors,
            }

            try:
                from app.core.config import settings
                storage_state = getattr(settings, 'BROWSER_STORAGE_STATE', None)
                if storage_state:
                    context_args["storage_state"] = storage_state
            except Exception:
                pass

            self._context = await self._browser.new_context(**context_args)
            self._page = await self._context.new_page()
            self._page.set_default_timeout(self._config.timeout)

            logger.info(f"浏览器初始化完成 (headless={effective_headless}, type={self._config.browser_type.value})")

        except ImportError as e:
            raise BrowserNotInitializedError(f"Playwright未安装: {e}")
        except Exception as e:
            await self._cleanup_resources()
            raise BrowserNotInitializedError(f"浏览器初始化失败: {e}")

    @handle_browser_errors
    async def close(self) -> None:
        """关闭浏览器并释放所有资源

        调用_cleanup_resources按逆序关闭Page → Context → Browser → Playwright。
        """
        await self._cleanup_resources()
        logger.info("浏览器已关闭")

    async def _cleanup_resources(self) -> None:
        """安全释放所有浏览器资源

        按Page → Context → Browser → Playwright的逆序关闭，
        每一层都使用try-except包裹，确保某层关闭失败不影响其他层的清理。
        最终将所有引用置为None，防止悬空引用。
        """
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
