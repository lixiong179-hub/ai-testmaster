"""批量定位模型 - 定义批量定位的状态、配置和结果数据结构。

本模块定义批量定位服务所需的所有枚举和数据模型，
被BatchLocatorService和BatchExecutorMixin共同依赖。

核心枚举:
    - BatchRecordStatus: 批量记录状态（PENDING/RUNNING/COMPLETED/FAILED/PARTIAL）

核心数据类:
    - BatchLocatorConfig: 批量定位配置
    - StepRecordResult: 步骤定位结果
    - BatchRecordReport: 批量定位报告
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


class BatchRecordStatus(str, Enum):
    """批量记录状态枚举 - 标识批量定位任务的执行状态。"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 全部完成
    FAILED = "failed"        # 全部失败
    PARTIAL = "partial"      # 部分完成


@dataclass
class BatchLocatorConfig:
    """批量定位配置 - 控制批量定位的行为参数。

    属性:
        skip_existing: 是否跳过已定位的步骤，默认True。
        execute_precondition: 是否执行前置条件步骤的定位，默认True。
        max_retries: 单个步骤最大重试次数，默认3。
        retry_delay: 重试间隔秒数，默认2。
        timeout: 单个步骤超时秒数，默认60。
        use_mcp: 是否使用MCP识别器，默认False。
    """
    skip_existing: bool = True
    execute_precondition: bool = True
    max_retries: int = 3
    retry_delay: int = 2
    timeout: int = 60
    use_mcp: bool = False


@dataclass
class StepRecordResult:
    """步骤定位结果 - 记录单个步骤的定位详情。

    属性:
        step_id: 步骤ID。
        step_number: 步骤序号。
        status: 定位状态。
        locator_type: 定位器类型（css/xpath/ai_coordinate）。
        locator_value: 定位器值。
        confidence: AI识别置信度。
        error_message: 错误信息。
        duration_ms: 定位耗时（毫秒）。
    """
    step_id: int
    step_number: int
    status: BatchRecordStatus = BatchRecordStatus.PENDING
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "step_id": self.step_id,
            "step_number": self.step_number,
            "status": self.status.value,
            "locator_type": self.locator_type,
            "locator_value": self.locator_value,
            "confidence": self.confidence,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BatchRecordReport:
    """批量定位报告 - 汇总整个批量定位任务的结果。

    属性:
        case_id: 测试用例ID。
        status: 整体状态。
        total_steps: 总步骤数。
        completed_steps: 完成步骤数。
        failed_steps: 失败步骤数。
        skipped_steps: 跳过步骤数。
        results: 各步骤定位结果列表。
        duration_ms: 总耗时（毫秒）。
    """
    case_id: int
    status: BatchRecordStatus = BatchRecordStatus.PENDING
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    results: List[StepRecordResult] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "case_id": self.case_id,
            "status": self.status.value,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "results": [r.to_dict() for r in self.results],
            "duration_ms": self.duration_ms,
        }
