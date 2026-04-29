"""批量定位子包 - 通过Mixin组合模式实现批量元素定位能力。

本子包是批量定位服务的核心实现，BatchLocatorService通过多继承
组合BatchExecutorMixin，实现测试用例所有步骤的批量元素定位。

核心类:
    - BatchLocatorService: 批量定位服务主类

Mixin组合:
    - BatchExecutorMixin: 批量执行逻辑

执行流程:
    batch_record_locators -> BatchExecutorMixin.batch_record_locators
    -> 遍历步骤 -> ElementLocatorService.smart_locate -> 记录定位结果
"""
from app.services.batch_locator.models import (
    BatchRecordStatus,
    BatchLocatorConfig,
    StepRecordResult,
    BatchRecordReport,
)
from app.services.batch_locator.batch_executor_mixin import BatchExecutorMixin
from app.services.batch_locator.task_manager import BatchTaskManager


class BatchLocatorService(BatchExecutorMixin):
    """批量定位服务 - 对测试用例的所有步骤进行批量元素定位。

    继承BatchExecutorMixin获取批量执行能力，本类负责
    服务初始化和配置管理。

    使用场景:
        - 用例详情页一键批量定位
        - 任务执行前预定位所有步骤元素
        - 定位覆盖率统计

    配置参数:
        - skip_existing: 是否跳过已定位步骤
        - execute_precondition: 是否执行前置条件定位
        - use_mcp: 是否使用MCP识别器
    """

    def __init__(
        self,
        progress_callback=None,
        config=None,
        use_mcp=None
    ):
        """初始化批量定位服务。

        Args:
            progress_callback: 进度回调函数，可选。
            config: 批量定位配置，可选。
            use_mcp: 是否使用MCP识别器，可选。
        """
        self._progress_callback = progress_callback
        self._config = config or BatchLocatorConfig()
        self._use_mcp = use_mcp


__all__ = [
    'BatchLocatorService',
    'BatchRecordStatus',
    'BatchLocatorConfig',
    'StepRecordResult',
    'BatchRecordReport',
    'BatchExecutorMixin',
    'BatchTaskManager',
]
