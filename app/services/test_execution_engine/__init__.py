"""测试执行引擎子包 - 通过Mixin组合模式实现Web端测试执行能力。

本子包是测试执行引擎的核心实现，TestExecutionEngineV2通过多继承
组合各功能Mixin，实现Web端测试的完整执行流程。

核心类:
    - TestExecutionEngineV2: 测试执行引擎主类

Mixin组合（MRO顺序）:
    - TaskBatchExecutorMixin: 任务批量执行
    - DependencyResolutionMixin: 依赖解析与快照容错
    - PreconditionMixin: 前置条件执行
    - SelfHealingExecuteMixin: 自愈执行
    - SelfHealingStagehandMixin: Stagehand云服务自愈
    - SelfHealingStrategyMixin: 自愈策略
    - SelfHealingUtilsMixin: 自愈工具方法
    - AIRecognitionMixin: AI视觉识别
    - ActionExecutorMixin: 动作执行分发
    - TestDataMixin: 测试数据管理
    - TaskExecutorMixin: 任务执行编排

执行流程:
    execute_test_task -> TaskBatchExecutorMixin.execute_test_task
    -> DependencyResolutionMixin: 依赖解析 + 拓扑排序 + 快照管理
    execute_test_case -> TaskExecutorMixin.execute_test_case
    -> [循环] _execute_step -> ActionExecutorMixin.execute_action
    -> 按action_type分发到具体Mixin -> AI识别/AI自愈/动作执行

容错策略:
    主干用例失败 -> _mark_dependents_blocked 标记下游 BLOCKED
    依赖用例执行前 -> _navigate_to_dependency_anchor 三级降级导航
    Level1: 快照恢复(storage_state+URL) -> Level2: fallback_steps -> Level3: 直接URL
"""
from typing import Optional

from app.services.test_execution_engine.models import (
    ExecutionStatus,
    ActionType,
    ExecutionMode,
    ExecutionError,
    StepExecutionError,
    VerificationError,
    StepExecutionResult,
    TestExecutionResult,
    FailureCategory,
    handle_execution_errors,
)
from app.services.test_execution_engine.action_executor_mixin import ActionExecutorMixin
from app.services.test_execution_engine.ai_recognition_mixin import AIRecognitionMixin
from app.services.test_execution_engine.api_setup_mixin import ApiSetupMixin
from app.services.test_execution_engine.dependency_resolution_mixin import DependencyResolutionMixin
from app.services.test_execution_engine.precondition_mixin import PreconditionMixin
from app.services.test_execution_engine.self_healing_execute_mixin import SelfHealingExecuteMixin
from app.services.test_execution_engine.self_healing_stagehand_mixin import SelfHealingStagehandMixin
from app.services.test_execution_engine.self_healing_strategy_mixin import SelfHealingStrategyMixin
from app.services.test_execution_engine.self_healing_utils_mixin import SelfHealingUtilsMixin
from app.services.test_execution_engine.step_executor_mixin import StepExecutorMixin
from app.services.test_execution_engine.task_executor_mixin import TaskExecutorMixin
from app.services.test_execution_engine.task_batch_executor_mixin import TaskBatchExecutorMixin
from app.services.test_execution_engine.test_data_mixin import TestDataMixin

from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.services.test_data import TestDataGenerator as TestDataService
from app.services.visibility_config import VisibilityConfigService
from app.utils.browser_controller_v2 import BrowserControllerV2
from app.utils.unified_vision_model import UnifiedVisionModel
from app.services.test_execution_engine import action_executor_verify_captcha_mixin as _captcha_mixin_module
from app.services.test_execution_engine.structured_assertion_mixin import (
    StructuredAssertionMixin,
    _ASSERTION_PATTERN,
    _STRUCTURED_ASSERTION_PREFIXES,
    _EXTENDED_ASSERTION_PATTERN,
)

_captcha_mixin_module.ActionExecutorVerifyCaptchaMixin = StructuredAssertionMixin
_captcha_mixin_module._ASSERTION_PATTERN = _ASSERTION_PATTERN
_captcha_mixin_module._STRUCTURED_ASSERTION_PREFIXES = _STRUCTURED_ASSERTION_PREFIXES
_captcha_mixin_module._EXTENDED_ASSERTION_PATTERN = _EXTENDED_ASSERTION_PATTERN


class TestExecutionEngineV2(
    TaskBatchExecutorMixin,
    DependencyResolutionMixin,
    ApiSetupMixin,
    PreconditionMixin,
    SelfHealingExecuteMixin,
    SelfHealingStagehandMixin,
    SelfHealingStrategyMixin,
    SelfHealingUtilsMixin,
    AIRecognitionMixin,
    ActionExecutorMixin,
    TestDataMixin,
    StepExecutorMixin,
    TaskExecutorMixin,
):
    """测试执行引擎V2 - 通过Mixin组合实现Web端测试的完整执行能力。

    继承顺序遵循MRO规则，底层Mixin提供基础能力，上层Mixin
    依赖底层能力实现更复杂的功能。
    """

    DEFAULT_STEP_TIMEOUT = 30
    DEFAULT_VERIFY_TIMEOUT = 10
    MAX_RETRY_COUNT = 3

    def __init__(
        self,
        db=None,
        precondition_service: Optional[PreconditionService] = None,
        locator_service: Optional[ElementLocatorService] = None,
        browser: Optional[BrowserControllerV2] = None,
        vision_model: Optional[UnifiedVisionModel] = None,
        enable_ai_recognition: bool = True,
        enable_test_data_param: bool = True,
        mobile_device_id: Optional[str] = None,
        **kwargs
    ):
        """初始化测试执行引擎。

        Args:
            db: 数据库会话
            precondition_service: 前置条件服务
            locator_service: 元素定位服务
            browser: 浏览器控制器（V2版本）
            vision_model: 视觉模型
            enable_ai_recognition: 是否启用AI识别
            enable_test_data_param: 是否启用测试数据参数化
            mobile_device_id: 移动设备ID
        """
        self.db = db
        self.precondition_service = precondition_service
        self.locator_service = locator_service
        self.browser = browser
        self.vision_model = vision_model
        self._current_execution = None
        self._step_results = []
        self._visibility_config = None

        self.enable_ai_recognition = enable_ai_recognition
        self.enable_test_data_param = enable_test_data_param
        self.test_data_service: Optional[TestDataService] = None
        self.parameterizer = None

        if self.enable_test_data_param and db:
            self.test_data_service = TestDataService(db)

        self._stagehand_client = None
        self._stagehand_session_id = None
        self._self_healing_attempts = 0
        self._self_healing_successes = 0
        self._self_healing_stats = {
            "total_attempts": 0,
            "total_healed": 0,
            "failed_attempts": 0,
            "healed_steps": [],
            "strategy_usage": {},
        }
        self._mobile_device_id = mobile_device_id
        self._mobile_executor = None
        self._mcp_recognizer = None


__all__ = [
    'TestExecutionEngineV2',
    'ExecutionStatus',
    'ActionType',
    'ExecutionMode',
    'ExecutionError',
    'StepExecutionError',
    'VerificationError',
    'StepExecutionResult',
    'TestExecutionResult',
    'FailureCategory',
    'handle_execution_errors',
    'PreconditionMixin',
    'DependencyResolutionMixin',
    'ApiSetupMixin',
    'ActionExecutorMixin',
    'AIRecognitionMixin',
    'SelfHealingExecuteMixin',
    'SelfHealingStagehandMixin',
    'SelfHealingStrategyMixin',
    'SelfHealingUtilsMixin',
    'StepExecutorMixin',
    'TaskExecutorMixin',
    'TaskBatchExecutorMixin',
    'TestDataMixin',
]
