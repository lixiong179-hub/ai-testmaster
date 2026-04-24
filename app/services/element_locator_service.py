"""
元素定位服务 - 兼容代理模块

所有实现已迁移到 element_locator/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.element_locator import ElementLocatorService

__all__ = ["ElementLocatorService"]
