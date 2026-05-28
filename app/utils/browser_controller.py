"""Backward-compatible browser controller exports.

The implementation was split into browser_controller_v2 and mixin modules.
This module preserves the legacy import path used by older tests and callers.
"""
from app.utils.browser_controller_v2 import (
    BrowserConfig,
    BrowserControllerV2,
    BrowserError,
    BrowserNotInitializedError,
    BrowserType,
    ElementInfo,
    ElementNotFoundError,
    NavigationError,
    ScreenshotConfig,
    create_browser_controller_v2,
    handle_browser_errors,
    require_initialized,
)

BrowserController = BrowserControllerV2
create_browser_controller = create_browser_controller_v2

__all__ = [
    "BrowserType",
    "BrowserConfig",
    "BrowserError",
    "BrowserNotInitializedError",
    "NavigationError",
    "ElementNotFoundError",
    "ScreenshotConfig",
    "ElementInfo",
    "require_initialized",
    "handle_browser_errors",
    "BrowserController",
    "BrowserControllerV2",
    "create_browser_controller",
    "create_browser_controller_v2",
]
