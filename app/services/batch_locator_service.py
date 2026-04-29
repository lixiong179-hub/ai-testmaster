"""批量定位服务 - 统一导出入口，聚合批量定位所有组件。

本模块作为批量定位服务的对外统一入口，将分散在batch_locator
子包中的服务类、模型和Mixin集中导出，同时提供便捷的异步函数
用于快速执行批量定位操作。

核心导出:
    - BatchLocatorService: 批量定位服务主类
    - BatchRecordStatus: 批量记录状态枚举
    - BatchLocatorConfig: 批量定位配置
    - StepRecordResult: 步骤记录结果
    - BatchRecordReport: 批量记录报告
    - BatchExecutorMixin: 批量执行Mixin
    - BatchTaskManager: 批量任务管理器

核心函数:
    - batch_record_locators: 便捷异步函数，快速执行批量定位

依赖关系:
    - app.services.batch_locator: 批量定位子包

架构设计:
    批量定位服务负责对测试用例的所有步骤进行批量元素定位，
    支持跳过已定位步骤、执行前置条件、进度回调等特性。
    通过BatchTaskManager管理并发任务，BatchExecutorMixin
    实现具体的批量执行逻辑。
"""
from typing import Optional, Callable, Dict, Any

from app.services.batch_locator import BatchLocatorService
from app.services.batch_locator.models import (
    BatchRecordStatus,
    BatchLocatorConfig,
    StepRecordResult,
    BatchRecordReport,
)
from app.services.batch_locator.batch_executor_mixin import BatchExecutorMixin
from app.services.batch_locator.task_manager import BatchTaskManager


async def batch_record_locators(
    case_id: int,
    skip_existing: bool = True,
    execute_precondition: bool = True,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    config: Optional[BatchLocatorConfig] = None,
    use_mcp: Optional[bool] = None
) -> BatchRecordReport:
    """便捷异步函数 - 快速执行批量元素定位。

    内部创建BatchLocatorService实例并调用batch_record_locators方法，
    适用于不需要复用服务实例的一次性批量定位场景。

    Args:
        case_id: 测试用例ID。
        skip_existing: 是否跳过已定位的步骤，默认True。
        execute_precondition: 是否执行前置条件步骤的定位，默认True。
        progress_callback: 进度回调函数，可选。
        config: 批量定位配置，可选。
        use_mcp: 是否使用MCP识别器，可选。

    Returns:
        BatchRecordReport批量定位报告。
    """
    service = BatchLocatorService(
        progress_callback=progress_callback,
        config=config,
        use_mcp=use_mcp
    )
    return await service.batch_record_locators(
        case_id=case_id,
        skip_existing=skip_existing,
        execute_precondition=execute_precondition
    )


__all__ = [
    'BatchLocatorService',
    'BatchRecordStatus',
    'BatchLocatorConfig',
    'StepRecordResult',
    'BatchRecordReport',
    'BatchExecutorMixin',
    'BatchTaskManager',
    'batch_record_locators',
]
