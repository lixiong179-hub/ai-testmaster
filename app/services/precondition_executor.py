"""前置条件执行器Mixin - 浏览器初始化、被测对象信息读取与资源清理。

本模块实现前置条件的执行器逻辑，包括视觉模型初始化、被测对象信息
读取（Web/App配置解析）、浏览器启动与导航、资源清理等。作为
ExecutorMixin被PreconditionService组合使用。

核心类:
    - ExecutorMixin: 执行器Mixin

依赖关系:
    - app.models.project: Project ORM模型
    - app.utils.browser_controller_v2: 浏览器控制器
    - app.utils.crypto: 密码解密工具
    - app.services.precondition_parser: 数据模型与异常定义

被测对象信息读取流程:
    1. 从Project模型读取test_object_type（web/app）
    2. 解析web_env_configs JSON配置（可能多层嵌套）
    3. 读取URL、用户名、密码等配置
    4. 密码解密（加密存储，运行时解密）
    5. 读取App设备信息（device_id/app_package/app_activity）
    6. 按类型校验必填字段

安全设计:
    - 密码通过decrypt_password解密，禁止明文存储
    - 解密失败时记录警告但不抛出异常，允许手动输入
"""
import asyncio
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.models.project import Project
from app.utils.browser_controller_v2 import (
    BrowserControllerV2 as BrowserController,
    BrowserConfig,
    BrowserType,
)
from app.utils.crypto import decrypt_password
from app.services.precondition_parser import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    TestObjectInfo,
    PreconditionTimingConfig,
    handle_precondition_errors,
)


class ExecutorMixin:
    """前置条件执行器Mixin - 管理浏览器生命周期和被测对象信息。

    职责:
        - 初始化视觉模型
        - 读取并解析被测对象信息（Web/App配置）
        - 启动浏览器并导航到目标URL
        - 执行App前置条件（预留）
        - 清理浏览器资源

    设计意图:
        将执行器逻辑从登录逻辑中抽离，便于:
        1. 独立管理浏览器生命周期
        2. 支持不同的被测对象类型（Web/App）
        3. 与LoginMixin解耦

    使用场景:
        被PreconditionService通过多继承组合，
        在前置条件流程中提供浏览器管理和信息读取能力。
    """

    @handle_precondition_errors
    async def initialize(
        self,
        model_type=None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> 'ExecutorMixin':
        """初始化视觉模型，支持自定义模型和默认模型两种方式。

        Args:
            model_type: 视觉模型类型，可选。
            api_key: API密钥，可选。
            base_url: API基础URL，可选。
            model_name: 模型名称，可选。

        Returns:
            self，支持链式调用。
        """
        if model_type:
            from app.utils.unified_vision_model import UnifiedVisionModel
            self.vision_model = UnifiedVisionModel(
                model_type=model_type,
                api_key=api_key,
                base_url=base_url,
                model_name=model_name
            )
        else:
            from app.utils.unified_vision_model import get_default_vision_model
            self.vision_model = get_default_vision_model()
        logger.info("前置操作服务初始化完成")
        return self

    @handle_precondition_errors
    async def read_test_object_info(
        self,
        project: Project,
        env_config: Optional[Dict[str, Any]] = None
    ) -> TestObjectInfo:
        """从Project模型读取被测对象信息，支持Web和App两种类型。

        信息来源优先级:
            被测对象类型:
                1. project.test_object_type（显式配置）
                2. 从web_env_configs推断（有配置则为web）
                3. project.project_type（回退）
            环境配置:
                1. 传入的env_config参数
                2. project.web_env_configs（JSON解析）
            URL/用户名/密码:
                1. 环境配置中的值
                2. Project模型字段值

        Args:
            project: Project ORM实例。
            env_config: 环境配置覆盖，可选。

        Returns:
            TestObjectInfo实例，包含完整的被测对象信息。

        Raises:
            PreconditionConfigError: 配置缺失或无效。
        """
        logger.info(f"读取项目 {project.name} 的被测对象信息")

        # 解析web_env_configs，支持dict/str/嵌套str格式
        def _parse_web_env_configs(raw) -> Optional[Dict[str, Any]]:
            if not raw:
                return None
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed
                    # 处理双重JSON编码的情况
                    if isinstance(parsed, str):
                        inner = json.loads(parsed)
                        if isinstance(inner, dict):
                            return inner
                except (json.JSONDecodeError, ValueError):
                    pass
            return None

        resolved_env_configs = _parse_web_env_configs(getattr(project, 'web_env_configs', None))

        # 推断被测对象类型
        raw_obj_type = None
        if hasattr(project, 'test_object_type') and getattr(project, 'test_object_type', None):
            raw_obj_type = project.test_object_type
        elif resolved_env_configs:
            raw_obj_type = "web"
            logger.info("从 web_env_configs 推断被测对象类型为 Web")
        elif hasattr(project, 'project_type') and getattr(project, 'project_type', None):
            raw_obj_type = project.project_type
            logger.info(f"从 project_type 推断被测对象类型为 {raw_obj_type}")

        if not raw_obj_type:
            raise PreconditionConfigError(
                "项目未配置被测对象类型，且无法从 web_env_configs 推断。"
                "请在项目中配置被测对象类型(web/app)或填写 Web环境配置。"
            )

        try:
            obj_type = TestObjectType(raw_obj_type.lower())
        except ValueError:
            raise PreconditionConfigError(f"无效的被测对象类型: {raw_obj_type}")

        # 合并环境配置，优先使用传入参数
        effective_env_config = env_config if (env_config and isinstance(env_config, dict)) else None
        if not effective_env_config and resolved_env_configs:
            effective_env_config = resolved_env_configs
        env_url = effective_env_config.get("url") if effective_env_config else None
        env_username = effective_env_config.get("username") if effective_env_config else None
        env_password = effective_env_config.get("password") if effective_env_config else None

        # 读取URL、用户名、密码，环境配置优先于Project字段
        target_url = env_url or getattr(project, 'test_object_url', None) or None
        target_username = env_username or getattr(project, 'test_object_username', None) or None
        raw_password = env_password or getattr(project, 'test_object_password', None) or None

        # 密码解密，解密失败时记录警告但不阻断流程
        decrypted_password = None
        if raw_password:
            try:
                decrypted_password = decrypt_password(raw_password)
            except Exception as e:
                logger.warning(f"密码解密失败（可能需要重新配置加密密钥）: {e}")
                decrypted_password = None

        info = TestObjectInfo(
            type=obj_type,
            url=target_url,
            username=target_username,
            password=decrypted_password
        )

        # 读取App设备信息
        device_info_raw = getattr(project, 'test_object_device_info', None)
        if device_info_raw and isinstance(device_info_raw, str):
            try:
                device_info = json.loads(device_info_raw)
                info.device_id = device_info.get("device_id")
            except json.JSONDecodeError as e:
                logger.warning(f"设备信息JSON解析失败: {e}")

        info.app_package = getattr(project, 'test_object_app_package', None)
        info.app_activity = getattr(project, 'test_object_app_activity', None)

        # 按类型校验必填字段
        if obj_type == TestObjectType.WEB:
            info.validate_web()
        elif obj_type == TestObjectType.APP:
            info.validate_app()

        self._test_object_info = info
        logger.info(f"被测对象信息读取成功: {obj_type.value}")
        return info

    @handle_precondition_errors
    async def execute_web_precondition(
        self,
        headless: bool = False,
        browser_type: str = "chromium",
        auto_login: bool = True
    ) -> BrowserController:
        """执行Web前置条件：启动浏览器、导航到目标URL、自动登录。

        Args:
            headless: 是否无头模式运行浏览器，默认False。
            browser_type: 浏览器类型，默认chromium。
            auto_login: 是否自动登录，默认True。

        Returns:
            初始化完成的BrowserController实例。

        Raises:
            PreconditionConfigError: 未读取被测对象信息或类型不匹配。
        """
        if not self._test_object_info:
            raise PreconditionConfigError("未读取被测对象信息，请先调用 read_test_object_info")
        if self._test_object_info.type != TestObjectType.WEB:
            raise PreconditionConfigError(f"当前项目类型不是Web: {self._test_object_info.type.value}")

        info = self._test_object_info
        logger.info(f"开始执行Web前置操作: {info.url}")

        # 配置并启动浏览器
        config = BrowserConfig(
            browser_type=BrowserType(browser_type),
            headless=headless,
            viewport_width=1920,
            viewport_height=1080
        )
        self.browser_controller = BrowserController(config)
        await self.browser_controller.initialize()
        logger.info("真实浏览器启动成功")

        # 导航到目标URL
        await self.browser_controller.navigate(info.url)
        logger.info(f"页面导航完成: {info.url}")

        # 自动登录（配置了用户名和密码时）
        if auto_login and info.username and info.password:
            logger.info(f"开始自动登录，用户名: {info.username}")
            await self._perform_login(info.username, info.password)

        logger.info("Web前置操作执行完成")
        return self.browser_controller

    @handle_precondition_errors
    async def execute_app_precondition(
        self,
        auto_login: bool = True,
        no_reset: bool = False
    ) -> Any:
        """执行App前置条件（当前已移除Appium依赖，预留接口）。

        Args:
            auto_login: 是否自动登录，默认True。
            no_reset: 是否不重置App状态，默认False。

        Returns:
            当前返回None，需使用移动端执行引擎替代。

        Note:
            Appium依赖已移除，请使用mobile_realtime/mobile_smart模式。
        """
        if not self._test_object_info:
            raise PreconditionConfigError("未读取被测对象信息，请先调用 read_test_object_info")
        if self._test_object_info.type != TestObjectType.APP:
            raise PreconditionConfigError(f"当前项目类型不是App: {self._test_object_info.type.value}")

        info = self._test_object_info
        logger.info(f"开始执行C端前置操作: {info.app_package}")
        logger.warning("Appium依赖已移除，请使用移动端执行引擎(mobile_realtime/mobile_smart)模式")
        return None

    @handle_precondition_errors
    async def cleanup(self) -> None:
        """清理浏览器资源，关闭浏览器实例。"""
        if self.browser_controller:
            await self.browser_controller.close()
            self.browser_controller = None
            logger.info("浏览器资源已清理")

    @property
    def is_browser_ready(self) -> bool:
        """检查浏览器是否已初始化并可用。"""
        return self.browser_controller is not None and self.browser_controller.is_initialized

    @property
    def test_object_info(self) -> Optional[TestObjectInfo]:
        """获取已读取的被测对象信息。"""
        return self._test_object_info
