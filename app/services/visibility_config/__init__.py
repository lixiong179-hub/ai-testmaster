"""
可见模式配置服务 - 兼容代理模块

所有实现已迁移到 visibility_config/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.visibility_config.models import VisibilityConfig, VisibilityLevel
from app.services.visibility_config.core_mixin import VisibilityConfigCoreMixin
from app.services.visibility_config.permission_mixin import VisibilityConfigPermissionMixin


class VisibilityConfigService(VisibilityConfigCoreMixin, VisibilityConfigPermissionMixin):
    """可见模式配置服务"""
    pass


# 全局配置服务实例
_visibility_config_service: VisibilityConfigService = None


def get_visibility_config_service() -> VisibilityConfigService:
    """获取可见模式配置服务实例（单例）"""
    global _visibility_config_service
    if _visibility_config_service is None:
        _visibility_config_service = VisibilityConfigService()
    return _visibility_config_service


__all__ = [
    "VisibilityConfig",
    "VisibilityLevel",
    "VisibilityConfigService",
    "get_visibility_config_service",
]
