"""测试执行引擎 V2 - 兼容性入口模块。

本模块仅作为向后兼容的导入入口，所有实现已迁移至
app.services.test_execution_engine 子包的各Mixin模块中。

迁移映射:
    - 枚举/数据类/装饰器 -> models.py
    - execute_test_case / _execute_step -> task_executor_mixin.py
    - execute_test_task / _get_task_summary -> task_batch_executor_mixin.py
    - 前置条件方法 -> precondition_mixin.py
    - AI识别方法 -> ai_recognition_mixin.py
    - 自愈执行方法 -> self_healing_execute_mixin.py
    - 自愈策略方法 -> self_healing_strategy_mixin.py
    - 测试数据方法 -> test_data_mixin.py
    - 动作执行方法 -> action_executor_*_mixin.py
"""
from app.services.test_execution_engine import (
    TestExecutionEngineV2,
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
]
