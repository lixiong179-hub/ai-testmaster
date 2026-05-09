"""浏览器控制器 hover 方法单元测试。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.utils.browser_controller_base import BrowserError


class TestBrowserHover:
    """测试 ActionMixin.hover 方法的参数校验逻辑（无需真实浏览器）。"""

    def _build_action_mixin(self):
        from app.utils.browser_controller_actions import ActionMixin

        mixin = ActionMixin()
        mixin._is_initialized = True
        mixin._page = MagicMock()
        mixin._page.mouse = MagicMock()
        mixin._page.mouse.move = AsyncMock()
        return mixin

    @pytest.mark.asyncio
    async def test_hover_normal_coordinates(self):
        mixin = self._build_action_mixin()
        await mixin.hover(100, 200)
        mixin._page.mouse.move.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_hover_zero_coordinates(self):
        mixin = self._build_action_mixin()
        await mixin.hover(0, 0)
        mixin._page.mouse.move.assert_called_once_with(0, 0)

    @pytest.mark.asyncio
    async def test_hover_negative_x_raises_browser_error(self):
        mixin = self._build_action_mixin()
        with pytest.raises(BrowserError, match="坐标必须非负"):
            await mixin.hover(-1, 100)

    @pytest.mark.asyncio
    async def test_hover_negative_y_raises_browser_error(self):
        mixin = self._build_action_mixin()
        with pytest.raises(BrowserError, match="坐标必须非负"):
            await mixin.hover(100, -1)

    @pytest.mark.asyncio
    async def test_hover_both_negative_raises_browser_error(self):
        mixin = self._build_action_mixin()
        with pytest.raises(BrowserError, match="坐标必须非负"):
            await mixin.hover(-5, -10)

    @pytest.mark.asyncio
    async def test_hover_boundary_large_coordinates(self):
        mixin = self._build_action_mixin()
        await mixin.hover(9999, 9999)
        mixin._page.mouse.move.assert_called_once_with(9999, 9999)
