
"""前置条件服务 - 通过Mixin组合模式组装测试前置条件执行能力。"""
from app.services.precondition.models import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    LoginError,
    TestObjectInfo,
    LoginFormInfo,
    MobileLoginFormInfo,
    MobileAppConfig,
    PreconditionTimingConfig,
)
from app.services.precondition.decorator import handle_precondition_errors
from app.services.precondition.utils import solve_captcha_math, recognize_login_form
from app.services.precondition.executor_mixin import ExecutorMixin
from app.services.precondition.login_mixin import LoginMixin
from app.utils.unified_vision_model import VisionModelType


class PreconditionService(LoginMixin, ExecutorMixin):
    """前置条件服务 - 组合Login和Executor两个Mixin。"""

    def __init__(self, timing_config: PreconditionTimingConfig | None = None) -> None:
        self.browser_controller = None
        self.vision_model = None
        self._test_object_info = None
        self._timing_config = timing_config or PreconditionTimingConfig()


async def create_precondition_service(
    model_type: VisionModelType = None,
    api_key: str = None,
    base_url: str = None,
    model_name: str = None,
    timing_config: PreconditionTimingConfig = None
) -> PreconditionService:
    """异步工厂函数 - 创建并初始化前置条件服务实例。"""
    service = PreconditionService(timing_config=timing_config)
    await service.initialize(
        model_type=model_type,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name
    )
    return service


PreconditionExecutorService = PreconditionService


__all__ = [
    "TestObjectType",
    "PreconditionError",
    "PreconditionConfigError",
    "LoginError",
    "TestObjectInfo",
    "LoginFormInfo",
    "MobileLoginFormInfo",
    "MobileAppConfig",
    "PreconditionTimingConfig",
    "handle_precondition_errors",
    "solve_captcha_math",
    "recognize_login_form",
    "PreconditionService",
    "PreconditionExecutorService",
    "create_precondition_service",
]
