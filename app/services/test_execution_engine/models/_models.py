from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import functools
import traceback
from loguru import logger

from app.services.test_execution_engine.models._enums import (
    ExecutionStatus,
    FailureCategory,
    ActionType,
    ExecutionMode,
)


class ExecutionError(Exception):
    pass


class StepExecutionError(ExecutionError):
    pass


class VerificationError(ExecutionError):
    pass


@dataclass
class StepExecutionResult:
    step_number: int
    action_type: ActionType = ActionType.CLICK
    action: str = ""
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
    failure_category: Optional[FailureCategory] = None
    retry_count: int = 0
    execution_detail: Optional[str] = None
    screenshot: Optional[Any] = None
    ai_analysis: Optional[str] = None
    element_locator: Optional[str] = None
    defect_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self, hidden_fields: Optional[list] = None) -> Dict[str, Any]:
        result = {
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
            "failure_category": self.failure_category.value if self.failure_category else None,
            "retry_count": self.retry_count,
        }
        if hidden_fields:
            for f in hidden_fields:
                result.pop(f, None)
        return result


@dataclass
class TestExecutionResult:
    __test__ = False

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
    failure_category: Optional[FailureCategory] = None
    navigation_level: Optional[str] = None

    def to_dict(self, hidden_fields: Optional[list] = None) -> Dict[str, Any]:
        result = {
            "case_id": self.case_id,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "healing_count": self.healing_count,
            "failure_category": self.failure_category.value if self.failure_category else None,
            "navigation_level": self.navigation_level,
            "steps": [s.to_dict(hidden_fields=hidden_fields) for s in self.steps],
        }
        if hidden_fields:
            for f in hidden_fields:
                result.pop(f, None)
        return result


@dataclass
class ExecutionConfig:
    timeout: int = 30
    retry_count: int = 0
    screenshot_on_failure: bool = False


@dataclass
class ExecutionResult:
    status: str
    duration: float = 0.0
    steps_passed: int = 0
    steps_failed: int = 0


def handle_execution_errors(func: Callable[..., Any]) -> Callable[..., Any]:
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
