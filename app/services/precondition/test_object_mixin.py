
"""前置条件数据对象Mixin - 管理被测对象信息的读取和解析。"""
import json
from typing import Optional, Dict, Any

from loguru import logger

from app.models.project import Project
from app.utils.crypto import decrypt_password
from app.services.precondition.models import (
    TestObjectType,
    PreconditionConfigError,
    TestObjectInfo,
    PreconditionTimingConfig,
)
from app.services.precondition.decorator import handle_precondition_errors


class TestObjectInfoMixin:
    """被测对象信息Mixin - 管理Web/App配置解析。"""

    _test_object_info: Optional[TestObjectInfo] = None

    @handle_precondition_errors
    async def read_test_object_info(
        self,
        project: Project,
        env_config: Optional[Dict[str, Any]] = None
    ) -> TestObjectInfo:
        """从Project模型读取被测对象信息。"""
        logger.info(f"读取项目 {project.name} 的被测对象信息")

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
                    if isinstance(parsed, str):
                        inner = json.loads(parsed)
                        if isinstance(inner, dict):
                            return inner
                except (json.JSONDecodeError, ValueError):
                    pass
            return None

        resolved_env_configs = _parse_web_env_configs(getattr(project, 'web_env_configs', None))

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

        effective_env_config = env_config if (env_config and isinstance(env_config, dict)) else None
        if not effective_env_config and resolved_env_configs:
            effective_env_config = resolved_env_configs
        env_url = effective_env_config.get("url") if effective_env_config else None
        env_username = effective_env_config.get("username") if effective_env_config else None
        env_password = effective_env_config.get("password") if effective_env_config else None

        target_url = env_url or getattr(project, 'test_object_url', None) or None
        target_username = env_username or getattr(project, 'test_object_username', None) or None
        raw_password = env_password or getattr(project, 'test_object_password', None) or None

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

        device_info_raw = getattr(project, 'test_object_device_info', None)
        if device_info_raw and isinstance(device_info_raw, str):
            try:
                device_info = json.loads(device_info_raw)
                info.device_id = device_info.get("device_id")
            except json.JSONDecodeError as e:
                logger.warning(f"设备信息JSON解析失败: {e}")

        info.app_package = getattr(project, 'test_object_app_package', None)
        info.app_activity = getattr(project, 'test_object_app_activity', None)

        if obj_type == TestObjectType.WEB:
            info.validate_web()
        elif obj_type == TestObjectType.APP:
            info.validate_app()

        self._test_object_info = info
        logger.info(f"被测对象信息读取成功: {obj_type.value}")
        return info

    @property
    def test_object_info(self) -> Optional[TestObjectInfo]:
        """获取已读取的被测对象信息。"""
        return self._test_object_info
