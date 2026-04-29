"""测试执行引擎模型 - 定义执行状态、动作类型、异常类和结果模型。

本模块定义测试执行引擎所需的所有枚举、异常类和数据模型，
被引擎主类和各Mixin共同依赖。

核心枚举:
    - ExecutionStatus: 执行状态（PENDING/RUNNING/PASSED/FAILED/SKIPPED/ERROR）
    - ActionType: 动作类型（CLICK/INPUT/SELECT/HOVER/VERIFY/NAVIGATE等）
    - ExecutionMode: 执行模式（AI_VISION/API/UNKNOWN）

核心异常:
    - ExecutionError: 执行基础异常
    - StepExecutionError: 步骤执行异常
    - VerificationError: 验证异常

核心模型:
    - StepExecutionResult: 步骤执行结果
    - TestExecutionResult: 测试执行结果

核心函数:
    - handle_execution_errors: 执行错误处理装饰器
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import functools
import traceback
from loguru import logger


class ExecutionStatus(str, Enum):
    """执行状态枚举 - 标识步骤和用例的执行状态。"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    PASSED = "passed"        # 通过
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过
    ERROR = "error"          # 异常


class ActionType(str, Enum):
    """动作类型枚举 - 标识测试步骤的操作类型。

    每种动作类型对应一个具体的执行器方法：
    - CLICK: 点击元素
    - INPUT: 输入文本
    - SELECT: 下拉选择
    - HOVER: 鼠标悬停
    - VERIFY: 验证元素状态
    - NAVIGATE: 页面导航
    - WAIT: 等待
    - SCREENSHOT: 截图
    - SCROLL: 滚动
    - DOUBLE_CLICK: 双击
    - RIGHT_CLICK: 右键点击
    - DRAG_AND_DROP: 拖拽
    - KEYBOARD: 键盘操作
    - UPLOAD: 文件上传
    - SWITCH_FRAME: 切换iframe
    - SWITCH_WINDOW: 切换窗口
    - CLOSE_WINDOW: 关闭窗口
    - REFRESH: 刷新页面
    - EXECUTE_SCRIPT: 执行JS脚本
    - VERIFY_CAPTCHA: 验证码验证
    - CUSTOM: 自定义动作
    """
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
    CUSTOM = "custom"


class ExecutionMode(str, Enum):
    """执行模式枚举 - 标识测试的执行方式。"""
    AI_VISION = "ai_vision"   # AI视觉模式
    API = "api"               # API模式
    UNKNOWN = "unknown"       # 未知模式


class ExecutionError(Exception):
    """执行基础异常 - 所有执行相关异常的基类。"""
    pass


class StepExecutionError(ExecutionError):
    """步骤执行异常 - 单个步骤执行失败时抛出。"""
    pass


class VerificationError(ExecutionError):
    """验证异常 - 验证步骤断言失败时抛出。"""
    pass


@dataclass
class StepExecutionResult:
    """步骤执行结果 - 记录单个步骤的执行详情。

    属性:
        step_number: 步骤序号。
        action_type: 动作类型。
        status: 执行状态。
        description: 步骤描述。
        start_time: 开始时间。
        end_time: 结束时间。
        duration_ms: 执行耗时（毫秒）。
        error_message: 错误信息。
        screenshot_path: 截图路径。
        element_info: 元素定位信息。
        healing_applied: 是否应用了自愈修复。
        original_selector: 原始选择器（自愈修复前）。
        healed_selector: 修复后的选择器。
    """
    step_number: int
    action_type: ActionType
    status: ExecutionStatus = ExecutionStatus.PENDING
    description: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: int = 0
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    element_info: Optional[Dict[str, Any]] = None
    healing_applied: bool = False
    original_selector: Optional[str] = None
    healed_selector: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "step_number": self.step_number,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "description": self.description,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "screenshot_path": self.screenshot_path,
            "healing_applied": self.healing_applied,
            "original_selector": self.original_selector,
            "healed_selector": self.healed_selector,
        }


@dataclass
class TestExecutionResult:
    """测试执行结果 - 记录整个测试用例的执行汇总。

    属性:
        case_id: 测试用例ID。
        status: 执行状态。
        start_time: 开始时间。
        end_time: 结束时间。
        duration_ms: 总执行耗时（毫秒）。
        steps: 步骤执行结果列表。
        error_message: 错误信息。
        total_steps: 总步骤数。
        passed_steps: 通过步骤数。
        failed_steps: 失败步骤数。
        healing_count: 自愈修复次数。
    """
    case_id: int
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: int = 0
    steps: List[StepExecutionResult] = field(default_factory=list)
    error_message: Optional[str] = None
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    healing_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "case_id": self.case_id,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "healing_count": self.healing_count,
            "steps": [s.to_dict() for s in self.steps],
        }


def handle_execution_errors(func):
    """执行错误处理装饰器 - 统一异常转换和日志记录。

    处理策略:
        - ExecutionError及其子类: 直接抛出
        - 其他异常: 转换为StepExecutionError，记录完整堆栈

    Args:
        func: 被装饰的异步函数。

    Returns:
        装饰后的异步函数。
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ExecutionError:
            raise
        except Exception as e:
            error_msg = f"{func.__name__} 执行失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            raise StepExecutionError(error_msg) from e
    return wrapper
