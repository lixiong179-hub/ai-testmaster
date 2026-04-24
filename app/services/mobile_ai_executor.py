"""
移动端AI执行器 - 兼容代理模块

所有实现已迁移到 mobile_ai_executor/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.mobile_ai_executor import (
    MobileAIExecutor,
    MobileActionType,
    MobileActionResult,
    MobileAIError,
    MobileDeviceError,
    MobileRecognitionError,
)

__all__ = [
    "MobileAIExecutor",
    "MobileActionType",
    "MobileActionResult",
    "MobileAIError",
    "MobileDeviceError",
    "MobileRecognitionError",
]
