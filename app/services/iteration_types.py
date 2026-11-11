"""迭代域异常与常量（R4-7：从 iteration_service 下沉，打破与 mixin 的循环导入）。

`iteration_service` 需要 `IterationAsyncMixin` 作为基类（运行时必需，
无法延迟导入），而 mixin 又需要本模块的异常类与状态迁移常量。
把后者下沉到独立模块后，依赖方向变为单向：

    iteration_service → iteration_types
    iteration_async_mixin → iteration_types
    iteration_service → iteration_async_mixin

`iteration_service` 仍 re-export 这些名字，既有
`from app.services.iteration_service import IterationStatusTransitionError`
用法不受影响。
"""
from app.models.enums import IterationInputKind, IterationPipelineStatus


class IterationStatusTransitionError(ValueError):
    """非法迭代状态迁移"""

    def __init__(self, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal iteration status transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class BaseIterationValidationError(ValueError):
    """基线迭代校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"Base iteration validation failed: {detail}")


class DuplicateInputHashError(ValueError):
    """重复输入哈希（幂等校验失败）"""

    def __init__(self, hash_value: str):
        super().__init__(f"Duplicate input hash: {hash_value}")


class IterationInputValidationError(ValueError):
    """迭代输入校验失败"""

    def __init__(self, detail: str):
        super().__init__(f"Iteration input validation failed: {detail}")


# 合法状态迁移路径
ITERATION_STATUS_TRANSITIONS = {
    (IterationPipelineStatus.DRAFT.value, IterationPipelineStatus.IN_PIPELINE.value),
    (IterationPipelineStatus.IN_PIPELINE.value, IterationPipelineStatus.IN_REVIEW.value),
    (IterationPipelineStatus.IN_REVIEW.value, IterationPipelineStatus.FINALIZED.value),
    (IterationPipelineStatus.FINALIZED.value, IterationPipelineStatus.ARCHIVED.value),
}

# IterationInputKind 合法值集合
VALID_INPUT_KINDS = {k.value for k in IterationInputKind}
