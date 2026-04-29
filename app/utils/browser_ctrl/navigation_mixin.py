"""
浏览器导航操作Mixin

提供页面导航相关功能，包括页面跳转、刷新、前进/后退、
页面信息获取和加载状态等待。

核心方法：
    - navigate: 导航到指定URL
    - get_page_info: 获取当前页面URL和标题
    - current_url: 当前页面URL属性
    - is_initialized: 浏览器是否已初始化属性
    - refresh: 刷新当前页面
    - go_back: 返回上一页
    - go_forward: 前进到下一页
    - wait_for_load_state: 等待页面加载状态

依赖：
    - app.utils.browser_ctrl.types: 装饰器和异常类
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.browser_ctrl.types import (
    require_initialized, handle_browser_errors, NavigationError,
)


class NavigationMixin:
    """浏览器导航操作Mixin

    提供页面级别的导航操作，与InteractionMixin（元素级操作）互补。
    包含页面跳转、刷新、前进后退等浏览器导航栏功能。
    """

    @handle_browser_errors
    @require_initialized
    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """导航到指定URL

        Args:
            url: 目标URL地址
            wait_until: 等待条件，可选值：
                - "domcontentloaded": DOM加载完成（默认，速度较快）
                - "load": 页面完全加载
                - "networkidle": 网络空闲（至少500ms无请求）

        Raises:
            NavigationError: 导航失败时抛出
        """
        try:
            await self._page.goto(url, wait_until=wait_until)
            logger.info(f"导航到: {url}")
        except Exception as e:
            raise NavigationError(f"导航失败: {url}, 错误: {e}")

    @handle_browser_errors
    @require_initialized
    async def get_page_info(self) -> Dict[str, Any]:
        """获取当前页面的基本信息

        Returns:
            Dict[str, Any]: 包含url和title的字典
        """
        return {
            "url": self._page.url,
            "title": await self._page.title(),
        }

    @property
    def current_url(self) -> Optional[str]:
        """获取当前页面URL

        Returns:
            Optional[str]: 当前URL，浏览器未初始化时返回None
        """
        if self._page:
            return self._page.url
        return None

    @property
    def is_initialized(self) -> bool:
        """检查浏览器是否已初始化

        Returns:
            bool: 已初始化返回True，否则返回False
        """
        return self._page is not None

    @handle_browser_errors
    @require_initialized
    async def refresh(self) -> None:
        """刷新当前页面"""
        await self._page.reload()
        logger.info("页面已刷新")

    @handle_browser_errors
    @require_initialized
    async def go_back(self) -> None:
        """返回上一页（浏览器后退）"""
        await self._page.go_back()
        logger.info("返回上一页")

    @handle_browser_errors
    @require_initialized
    async def go_forward(self) -> None:
        """前进到下一页（浏览器前进）"""
        await self._page.go_forward()
        logger.info("前进到下一页")

    @handle_browser_errors
    @require_initialized
    async def wait_for_load_state(self, state: str = "networkidle") -> None:
        """等待页面达到指定加载状态

        Args:
            state: 加载状态，可选值：
                - "networkidle": 网络空闲（默认，至少500ms无请求）
                - "domcontentloaded": DOM加载完成
                - "load": 页面完全加载
        """
        await self._page.wait_for_load_state(state)
