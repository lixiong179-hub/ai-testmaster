"""测试执行引擎子包 - 通过Mixin组合模式实现Web端测试执行能力。

本子包是测试执行引擎的核心实现，TestExecutionEngineV2通过多继承
组合各功能Mixin，实现Web端测试的完整执行流程。

核心类:
    - TestExecutionEngineV2: 测试执行引擎主类

Mixin组合（MRO顺序）:
    - PreconditionMixin: 前置条件执行
    - SelfHealingExecuteMixin: 自愈执行
    - SelfHealingStrategyMixin: 自愈策略
    - SelfHealingMixin: 自愈基础
    - AIRecognitionMixin: AI视觉识别
    - ActionExecutorVerifyCaptchaMixin: 验证码验证
    - ActionExecutorComplexMixin: 复杂动作执行
    - ActionExecutorHoverSelectMixin: 悬停选择动作
    - ActionExecutorInputClickMixin: 输入点击动作
    - ActionExecutorBasicMixin: 基础动作执行
    - ActionExecutorMixin: 动作执行分发
    - TestDataMixin: 测试数据管理
    - TaskExecutorMixin: 任务执行编排

执行流程:
    execute_test_task -> TaskExecutorMixin._execute_task
    -> [循环] _execute_test_step -> ActionExecutorMixin.execute_action
    -> 按action_type分发到具体Mixin -> AI识别/AI自愈/动作执行
"""
from app.services.test_execution_engine.models import (
    ExecutionStatus,
    ActionType,
    ExecutionMode,
    ExecutionError,
    StepExecutionError,
    VerificationError,
    StepExecutionResult,
    TestExecutionResult,
    handle_execution_errors,
)
from app.services.test_execution_engine.action_executor_mixin import ActionExecutorMixin
from app.services.test_execution_engine.action_executor_basic_mixin import ActionExecutorBasicMixin
from app.services.test_execution_engine.action_executor_input_click_mixin import ActionExecutorInputClickMixin
from app.services.test_execution_engine.action_executor_hover_select_mixin import ActionExecutorHoverSelectMixin
from app.services.test_execution_engine.action_executor_complex_mixin import ActionExecutorComplexMixin
from app.services.test_execution_engine.action_executor_verify_captcha_mixin import ActionExecutorVerifyCaptchaMixin
from app.services.test_execution_engine.ai_recognition_mixin import AIRecognitionMixin
from app.services.test_execution_engine.precondition_mixin import PreconditionMixin
from app.services.test_execution_engine.self_healing_mixin import SelfHealingMixin
from app.services.test_execution_engine.self_healing_execute_mixin import SelfHealingExecuteMixin
from app.services.test_execution_engine.self_healing_strategy_mixin import SelfHealingStrategyMixin
from app.services.test_execution_engine.task_executor_mixin import TaskExecutorMixin
from app.services.test_execution_engine.test_data_mixin import TestDataMixin


class TestExecutionEngineV2(
    PreconditionMixin,
    SelfHealingMixin,
    AIRecognitionMixin,
    ActionExecutorMixin,
    TestDataMixin,
    TaskExecutorMixin,
):
    """测试执行引擎V2 - 通过Mixin组合实现Web端测试的完整执行能力。

    继承顺序遵循MRO规则，底层Mixin提供基础能力，上层Mixin
    依赖底层能力实现更复杂的功能。

    使用场景:
        - Web端UI自动化测试执行
        - AI视觉识别驱动的元素定位
        - 自愈机制修复定位失败
        - 测试数据参数化解析

    初始化参数:
        db: 数据库会话
        headless: 是否无头模式
        record_video: 是否录制视频
    """

    def __init__(self, db=None, headless: bool = True, record_video: bool = False, **kwargs):
        """初始化测试执行引擎。

        Args:
            db: 数据库会话，可选。
            headless: 是否无头模式运行浏览器，默认True。
            record_video: 是否录制执行视频，默认False。
            **kwargs: 其他配置参数。
        """
        self.db = db
        self.headless = headless
        self.record_video = record_video
        self.browser_controller = None  # 浏览器控制器，延迟初始化
        self.vision_model = None  # 视觉模型，延迟初始化
        self._execution_context = {}  # 执行上下文，存储执行过程中的临时数据

        # AI自愈相关属性
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
        self._mobile_device_id = None
        self._mobile_executor = None


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
    'handle_execution_errors',
    'PreconditionMixin',
    'ActionExecutorMixin',
    'ActionExecutorBasicMixin',
    'ActionExecutorInputClickMixin',
    'ActionExecutorHoverSelectMixin',
    'ActionExecutorComplexMixin',
    'ActionExecutorVerifyCaptchaMixin',
    'AIRecognitionMixin',
    'SelfHealingMixin',
    'SelfHealingExecuteMixin',
    'SelfHealingStrategyMixin',
    'TaskExecutorMixin',
    'TestDataMixin',
]
