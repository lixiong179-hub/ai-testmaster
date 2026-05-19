from enum import Enum
from typing import Optional


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    ERROR = "error"


class FailureCategory(str, Enum):
    PRODUCT_BUG = "product_bug"
    UPSTREAM_BLOCKED = "upstream_blocked"
    NAVIGATION_FAILURE = "navigation_failure"
    PRECONDITION_FAILURE = "precondition_failure"
    LOCATOR_FAILURE = "locator_failure"
    ENVIRONMENT_ERROR = "environment_error"
    PERFORMANCE_BUG = "performance_bug"
    COMPATIBILITY_BUG = "compatibility_bug"
    CRASH_BUG = "crash_bug"

    @classmethod
    def is_product_bug(cls, category: Optional["FailureCategory"]) -> bool:
        if category is None:
            return False
        return category in (
            cls.PRODUCT_BUG,
            cls.PERFORMANCE_BUG,
            cls.COMPATIBILITY_BUG,
            cls.CRASH_BUG,
        )

    @classmethod
    def is_false_positive(cls, category: Optional["FailureCategory"]) -> bool:
        if category is None:
            return False
        return category in (
            cls.UPSTREAM_BLOCKED,
            cls.NAVIGATION_FAILURE,
            cls.PRECONDITION_FAILURE,
            cls.ENVIRONMENT_ERROR,
            cls.LOCATOR_FAILURE,
        )


class ActionType(str, Enum):
    CLICK = "click"
    INPUT = "input"
    SELECT = "select"
    HOVER = "hover"
    VERIFY = "verify"
    NAVIGATE = "navigate"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    SCROLL = "scroll"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    DRAG_AND_DROP = "drag_and_drop"
    KEYBOARD = "keyboard"
    UPLOAD = "upload"
    SWITCH_FRAME = "switch_frame"
    SWITCH_WINDOW = "switch_window"
    CLOSE_WINDOW = "close_window"
    REFRESH = "refresh"
    EXECUTE_SCRIPT = "execute_script"
    VERIFY_CAPTCHA = "verify_captcha"
    API_CALL = "api_call"
    CUSTOM = "custom"


class ExecutionMode(str, Enum):
    AI_VISION = "ai_vision"
    API = "api"
    UNKNOWN = "unknown"
