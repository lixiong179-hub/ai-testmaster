"""Visibility Config Service - 兼容代理模块

所有实现已迁移到 visibility_config/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.visibility_config import (
    VisibilityConfigService,
    VisibilityConfig,
    VisibilityLevel,
    get_visibility_config_service,
)

__all__ = [
    "VisibilityConfigService",
    "VisibilityConfig",
    "VisibilityLevel",
    "get_visibility_config_service",
]
