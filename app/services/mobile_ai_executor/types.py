"""移动端AI执行器类型定义 - 兼容原始 mobile_ai_executor.py。"""
import re
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class MobileActionType(str, Enum):
    CLICK = "click"
    INPUT = "input"
    SWIPE = "swipe"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    VERIFY = "verify"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    SCROLL_LEFT = "scroll_left"
    SCROLL_RIGHT = "scroll_right"
    LAUNCH_APP = "launch_app"
    GO_BACK = "go_back"
    GO_HOME = "go_home"


class MobileAIError(Exception):
    pass


class MobileDeviceError(MobileAIError):
    pass


class MobileRecognitionError(MobileAIError):
    pass


@dataclass
class MobileActionResult:
    success: bool
    action_type: MobileActionType
    description: str
    coordinates: Optional[Dict[str, int]] = None
    locator_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    ai_confidence: float = 0.0
    used_cache: bool = False
    cached_locator: Optional[Dict[str, Any]] = None
