"""移动端AI类型定义 - 定义移动端执行器的枚举、异常和结果模型。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MobileActionType(str, Enum):
    CLICK = "click"
    INPUT = "input"
    SWIPE = "swipe"
    PRESS_KEY = "press_key"
    VERIFY = "verify"
    WAIT = "wait"
    LAUNCH_APP = "launch_app"
    GO_BACK = "go_back"
    GO_HOME = "go_home"


@dataclass
class MobileActionResult:
    success: bool
    action_type: MobileActionType
    description: str = ""
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class MobileAIError(Exception):
    message: str = ""
    device_id: Optional[str] = None


@dataclass
class MobileDeviceError(MobileAIError):
    pass


@dataclass
class MobileRecognitionError(MobileAIError):
    pass
