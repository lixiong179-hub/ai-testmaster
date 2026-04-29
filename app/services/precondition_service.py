"""前置条件服务 - 通过Mixin组合模式组装测试前置条件执行能力。

本模块是前置条件体系的服务入口，通过多继承组合Login和Executor两个Mixin，
形成完整的前置条件服务。支持Web和App两种被测对象类型。

核心类:
    - PreconditionService: 前置条件服务，组合LoginMixin和ExecutorMixin

核心函数:
    - create_precondition_service: 异步工厂函数，创建并初始化服务实例

设计模式:
    采用Mixin组合模式，将前置条件的不同维度拆分到独立Mixin中:
    - LoginMixin: 登录操作（表单识别、验证码处理、登录状态检测）
    - ExecutorMixin: 执行器（初始化、被测对象信息读取、浏览器管理）

    PreconditionService通过多继承组合两个Mixin，对外提供统一的前置条件接口。

依赖关系:
    - app.services.precondition_parser: 数据模型与工具函数
    - app.services.precondition_executor: 执行器Mixin
    - app.services.precondition_login: 登录Mixin
    - app.utils.unified_vision_model: 统一视觉模型

前置条件流程:
    1. 读取被测对象信息（URL/用户名/密码等）
    2. 启动浏览器并导航到目标页面
    3. 自动识别登录表单
    4. 执行自动登录（含验证码处理）
    5. 验证登录状态

安全设计:
    - 密码通过crypto模块加密存储，运行时解密
    - 日志中密码字段脱敏为"敏感信息"
"""
from app.services.precondition_parser import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    LoginError,
    TestObjectInfo,
    LoginFormInfo,
    MobileLoginFormInfo,
    MobileAppConfig,
    PreconditionTimingConfig,
    handle_precondition_errors,
    solve_captcha_math,
    recognize_login_form,
)
from app.services.precondition_executor import ExecutorMixin
from app.services.precondition_login import LoginMixin
from app.utils.unified_vision_model import VisionModelType


class PreconditionService(LoginMixin, ExecutorMixin):
    """前置条件服务 - 组合Login和Executor两个Mixin的完整前置条件能力。

    继承顺序（MRO）:
        LoginMixin -> ExecutorMixin

        ExecutorMixin在底层，提供浏览器初始化和被测对象信息管理。
        LoginMixin在上层，提供登录表单识别和自动登录能力。

    使用场景:
        - 测试执行前的环境准备（打开浏览器、登录系统）
        - Web/App项目的自动登录
        - 验证码自动识别与处理

    使用方式:
        service = await create_precondition_service()
        await service.read_test_object_info(project)
        browser = await service.execute_web_precondition()
    """

    def __init__(self, timing_config: PreconditionTimingConfig | None = None) -> None:
        """初始化前置条件服务。

        Args:
            timing_config: 时序配置，控制登录等待、输入延迟等参数，可选。
        """
        self.browser_controller = None  # 浏览器控制器，延迟初始化
        self.vision_model = None  # 视觉模型，延迟初始化
        self._test_object_info = None  # 被测对象信息，延迟读取
        self._timing_config = timing_config or PreconditionTimingConfig()


async def create_precondition_service(
    model_type: VisionModelType = None,
    api_key: str = None,
    base_url: str = None,
    model_name: str = None,
    timing_config: PreconditionTimingConfig = None
) -> PreconditionService:
    """异步工厂函数 - 创建并初始化前置条件服务实例。

    Args:
        model_type: 视觉模型类型，可选。
        api_key: API密钥，可选。
        base_url: API基础URL，可选。
        model_name: 模型名称，可选。
        timing_config: 时序配置，可选。

    Returns:
        初始化完成的PreconditionService实例。
    """
    service = PreconditionService(timing_config=timing_config)
    await service.initialize(
        model_type=model_type,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name
    )
    return service


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
    "create_precondition_service",
]
