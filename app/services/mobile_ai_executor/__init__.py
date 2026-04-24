"""移动端AI执行器子包 - 通过AI视觉识别执行移动端测试操作。

核心类:
    - MobileAIExecutor: 移动端AI执行器主类

Mixin组合:
    - MobileActionParserMixin: 动作解析（自然语言到动作类型）
    - MobileActionExecutorMixin: 动作执行（点击、输入、滑动等）
    - MobileRecognitionMixin: 元素识别与缓存管理
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.utils.adb_controller import AdbController
from app.utils.uiautomator_helper import UIAutomatorHelper
from app.utils.unified_vision_model import UnifiedVisionModel, create_vision_model
from app.services.mobile_ai_executor.types import (
    MobileActionType, MobileActionResult,
    MobileAIError, MobileDeviceError, MobileRecognitionError,
)
from app.services.mobile_ai_executor.action_parser_mixin import MobileActionParserMixin
from app.services.mobile_ai_executor.action_executor_mixin import MobileActionExecutorMixin
from app.services.mobile_ai_executor.recognition_mixin import MobileRecognitionMixin


class MobileAIExecutor(
    MobileActionExecutorMixin,
    MobileRecognitionMixin,
    MobileActionParserMixin,
):
    """移动端AI执行器 - 通过AI视觉识别执行移动端测试操作。

    继承顺序（MRO）:
        MobileActionExecutorMixin -> MobileRecognitionMixin -> MobileActionParserMixin
    """

    def __init__(
        self,
        db: Session,
        adb: AdbController,
        vision_model: Optional[UnifiedVisionModel] = None,
        uiautomator: Optional[UIAutomatorHelper] = None,
    ):
        self.db = db
        self.adb = adb
        self.vision_model = vision_model or create_vision_model()
        self.uiautomator = uiautomator or UIAutomatorHelper(adb)


__all__ = [
    "MobileAIExecutor",
    "MobileActionType",
    "MobileActionResult",
    "MobileAIError",
    "MobileDeviceError",
    "MobileRecognitionError",
]
