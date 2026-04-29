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
    BrowserControllerV2 as _BrowserControllerV2Base,
)
from app.utils.browser_controller_navigation import NavigationMixin, ScreenshotConfig
from app.utils.browser_controller_actions import ActionMixin


class BrowserControllerV2(NavigationMixin, ActionMixin, _BrowserControllerV2Base):
    pass


async def create_browser_controller_v2(
    browser_type: str = "chromium",
    headless: bool = False,
    **kwargs
) -> BrowserControllerV2:
    config = BrowserConfig(
        browser_type=BrowserType(browser_type),
        headless=headless,
        **kwargs
    )
    controller = BrowserControllerV2(config)
    await controller.initialize()
    return controller


__all__ = [
    "BrowserType",
    "BrowserError",
    "BrowserNotInitializedError",
    "NavigationError",
    "ElementNotFoundError",
    "BrowserConfig",
    "ScreenshotConfig",
    "ElementInfo",
    "require_initialized",
    "handle_browser_errors",
    "BrowserControllerV2",
    "create_browser_controller_v2",
]
