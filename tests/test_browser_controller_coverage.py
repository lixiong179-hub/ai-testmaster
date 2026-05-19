"""
浏览器控制器覆盖率测试
提升 browser_controller.py 的测试覆盖率
"""
import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

from app.utils.browser_controller import (
    BrowserType,
    BrowserConfig,
    BrowserError,
    BrowserNotInitializedError,
    NavigationError,
    ElementNotFoundError
)


class TestBrowserType(unittest.TestCase):
    """测试浏览器类型枚举"""
    
    def test_browser_types(self):
        """测试所有浏览器类型"""
        self.assertEqual(BrowserType.CHROMIUM.value, "chromium")
        self.assertEqual(BrowserType.FIREFOX.value, "firefox")
        self.assertEqual(BrowserType.WEBKIT.value, "webkit")


class TestBrowserConfig(unittest.TestCase):
    """测试浏览器配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = BrowserConfig()
        self.assertEqual(config.browser_type, BrowserType.CHROMIUM)
        self.assertFalse(config.headless)  # 默认是False，表示显示浏览器窗口
        self.assertEqual(config.viewport_width, 1920)
        self.assertEqual(config.viewport_height, 1080)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = BrowserConfig(
            browser_type=BrowserType.FIREFOX,
            headless=False,
            viewport_width=1280,
            viewport_height=720
        )
        self.assertEqual(config.browser_type, BrowserType.FIREFOX)
        self.assertFalse(config.headless)
        self.assertEqual(config.viewport_width, 1280)
        self.assertEqual(config.viewport_height, 720)


class TestBrowserErrors(unittest.TestCase):
    """测试浏览器错误类"""
    
    def test_browser_error(self):
        """测试基础浏览器错误"""
        error = BrowserError("浏览器错误")
        self.assertEqual(str(error), "浏览器错误")
    
    def test_browser_not_initialized_error(self):
        """测试未初始化错误"""
        error = BrowserNotInitializedError("浏览器未初始化")
        self.assertEqual(str(error), "浏览器未初始化")
    
    def test_browser_navigation_error(self):
        """测试导航错误"""
        error = NavigationError("导航失败")
        self.assertEqual(str(error), "导航失败")
    
    def test_browser_element_not_found_error(self):
        """测试元素未找到错误"""
        error = ElementNotFoundError("元素未找到")
        self.assertEqual(str(error), "元素未找到")


if __name__ == '__main__':
    unittest.main(verbosity=2)
