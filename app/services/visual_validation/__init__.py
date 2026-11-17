"""视觉校验子包（R3-3）。

导出：
    - VisualValidationConfigService : 项目级开关与配置读写
    - is_visual_validation_enabled  : 执行链路开关判定（全局 AND 项目）
    - spawn_visual_validation_agent : fire-and-forget 触发视觉校验管线
"""
from app.services.visual_validation.config_service import (
    CONFIG_KEY,
    DEFAULT_VISUAL_VALIDATION_CONFIG,
    VisualValidationConfigService,
    resolve_enabled,
)
from app.services.visual_validation.service import (
    is_visual_validation_enabled,
    is_visual_validation_enabled_sync,
    spawn_visual_validation_agent,
)

__all__ = [
    "CONFIG_KEY",
    "DEFAULT_VISUAL_VALIDATION_CONFIG",
    "VisualValidationConfigService",
    "resolve_enabled",
    "is_visual_validation_enabled",
    "is_visual_validation_enabled_sync",
    "spawn_visual_validation_agent",
]
