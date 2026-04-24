
"""浏览器管理Mixin - 浏览器生命周期管理。"""
from typing import Any, Optional
from loguru import logger

from app.utils.browser_controller_v2 import (
    BrowserControllerV2 as BrowserController,
    BrowserConfig,
    BrowserType,
)
from app.services.precondition.models import (
    TestObjectType,
    PreconditionConfigError,
    TestObjectInfo,
)
from app.services.precondition.decorator import handle_precondition_errors


class BrowserMixin:
    """浏览器管理Mixin - 管理浏览器实例的创建、导航和清理。"""

    browser_controller: Optional[BrowserController] = None
    _test_object_info: Optional[TestObjectInfo] = None

    @handle_precondition_errors
    async def execute_web_precondition(
        self,
        headless: bool = False,
        browser_type: str = "chromium",
        auto_login: bool = True
    ) -> BrowserController:
        """执行Web前置条件：启动浏览器、导航到目标URL、自动登录。"""
        if not self._test_object_info:
            raise PreconditionConfigError("未读取被测对象信息，请先调用 read_test_object_info")
        if self._test_object_info.type != TestObjectType.WEB:
            raise PreconditionConfigError(f"当前项目类型不是Web: {self._test_object_info.type.value}")

        info = self._test_object_info
        logger.info(f"开始执行Web前置操作: {info.url}")

        config = BrowserConfig(
            browser_type=BrowserType(browser_type),
            headless=headless,
            viewport_width=1920,
            viewport_height=1080
        )
        self.browser_controller = BrowserController(config)
        await self.browser_controller.initialize()
        logger.info("真实浏览器启动成功")

        await self.browser_controller.navigate(info.url)
        logger.info(f"页面导航完成: {info.url}")

        if auto_login and info.username and info.password:
            logger.info(f"开始自动登录，用户名: {info.username}")
            await self._perform_login(info.username, info.password)

        logger.info("Web前置操作执行完成")
        return self.browser_controller

    @handle_precondition_errors
    async def execute_app_precondition(
        self,
        auto_login: bool = True,
        no_reset: bool = False
    ) -> Any:
        """执行App前置条件（预留接口）。"""
        if not self._test_object_info:
            raise PreconditionConfigError("未读取被测对象信息，请先调用 read_test_object_info")
        if self._test_object_info.type != TestObjectType.APP:
            raise PreconditionConfigError(f"当前项目类型不是App: {self._test_object_info.type.value}")

        info = self._test_object_info
        logger.info(f"开始执行C端前置操作: {info.app_package}")
        logger.warning("Appium依赖已移除，请使用移动端执行引擎(mobile_realtime/mobile_smart)模式")
        return None

    @handle_precondition_errors
    async def cleanup(self) -> None:
        """清理浏览器资源。"""
        if self.browser_controller:
            await self.browser_controller.close()
            self.browser_controller = None
            logger.info("浏览器资源已清理")

    @property
    def is_browser_ready(self) -> bool:
        """检查浏览器是否已初始化并可用。"""
        return self.browser_controller is not None and self.browser_controller.is_initialized
