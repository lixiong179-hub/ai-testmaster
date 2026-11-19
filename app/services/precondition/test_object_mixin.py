"""前置条件数据对象Mixin - 管理被测对象信息的读取和解析。"""

import json
from typing import Any

from loguru import logger

from app.models.project import Project
from app.utils.crypto import decrypt_password
from app.services.precondition.models import (
    TestObjectType,
    PreconditionConfigError,
    TestObjectInfo,
)
from app.services.precondition.decorator import handle_precondition_errors


def _parse_web_env_configs(raw) -> dict[str, Any] | None:
    """解析项目的 web_env_configs（dict / JSON 字符串 / 双层编码字符串）。"""
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


def _get_non_empty_string(obj: Any, attr: str) -> str | None:
    """取对象上的非空字符串属性（自动 strip）。"""
    value = getattr(obj, attr, None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _resolve_raw_object_type(project: Project, resolved_env_configs: dict | None) -> str:
    """按 test_object_type → web_env_configs → project_type 推断被测对象类型。"""
    test_object_type = _get_non_empty_string(project, "test_object_type")
    if test_object_type:
        return test_object_type
    if resolved_env_configs:
        logger.info("从 web_env_configs 推断被测对象类型为 Web")
        return "web"
    project_type = _get_non_empty_string(project, "project_type")
    if project_type:
        logger.info(f"从 project_type 推断被测对象类型为 {project_type}")
        return project_type
    raise PreconditionConfigError(
        "项目未配置被测对象类型，且无法从 web_env_configs 推断。请在项目中配置被测对象类型(web/app)或填写 Web环境配置。"
    )


def _coerce_object_type(raw_obj_type: str) -> TestObjectType:
    """把字符串转换为 TestObjectType，非法值抛配置错误。"""
    try:
        return TestObjectType(raw_obj_type.lower())
    except ValueError:
        raise PreconditionConfigError(f"无效的被测对象类型: {raw_obj_type}")


def _pick_env_config(env_config: dict[str, Any] | None, resolved_env_configs: dict | None) -> dict[str, Any] | None:
    """优先使用显式入参，其次回退项目 web_env_configs。"""
    if env_config and isinstance(env_config, dict):
        return env_config
    return resolved_env_configs or None


def _read_env_value(env_config: dict[str, Any] | None, key: str):
    """读取环境配置字段。"""
    return env_config.get(key) if env_config else None


def _decrypt_password_or_none(raw_password: str | None) -> str | None:
    """解密密码；失败仅告警并返回 None（不阻断流程）。"""
    if not raw_password:
        return None
    try:
        return decrypt_password(raw_password)
    except Exception as e:
        logger.warning(f"密码解密失败（可能需要重新配置加密密钥）: {e}")
        return None


def _read_device_id(project: Project) -> str | None:
    """从 test_object_device_info 读取设备 ID；JSON 非法时告警并返回 None。"""
    raw = getattr(project, "test_object_device_info", None)
    if not raw or not isinstance(raw, str):
        return None
    try:
        return json.loads(raw).get("device_id")
    except json.JSONDecodeError as e:
        logger.warning(f"设备信息JSON解析失败: {e}")
        return None


def _validate_test_object(info: TestObjectInfo, obj_type: TestObjectType) -> None:
    """按对象类型执行 Web / App 必填校验。"""
    if obj_type == TestObjectType.WEB:
        info.validate_web()
    elif obj_type == TestObjectType.APP:
        info.validate_app()


class TestObjectInfoMixin:
    """被测对象信息Mixin - 管理Web/App配置解析。"""

    _test_object_info: TestObjectInfo | None = None

    @handle_precondition_errors
    async def read_test_object_info(self, project: Project, env_config: dict[str, Any] | None = None) -> TestObjectInfo:
        """从Project模型读取被测对象信息。"""
        logger.info(f"读取项目 {project.name} 的被测对象信息")

        resolved_env_configs = _parse_web_env_configs(getattr(project, "web_env_configs", None))
        obj_type = _coerce_object_type(_resolve_raw_object_type(project, resolved_env_configs))

        effective_env_config = _pick_env_config(env_config, resolved_env_configs)

        target_url = _read_env_value(effective_env_config, "url") or getattr(project, "test_object_url", None) or None
        target_username = (
            _read_env_value(effective_env_config, "username") or getattr(project, "test_object_username", None) or None
        )
        raw_password = (
            _read_env_value(effective_env_config, "password") or getattr(project, "test_object_password", None) or None
        )

        info = TestObjectInfo(
            type=obj_type,
            url=target_url,
            username=target_username,
            password=_decrypt_password_or_none(raw_password),
        )

        device_id = _read_device_id(project)
        if device_id:
            info.device_id = device_id

        info.app_package = getattr(project, "test_object_app_package", None)
        info.app_activity = getattr(project, "test_object_app_activity", None)

        _validate_test_object(info, obj_type)

        self._test_object_info = info
        logger.info(f"被测对象信息读取成功: {obj_type.value}")
        return info

    @property
    def test_object_info(self) -> TestObjectInfo | None:
        """获取已读取的被测对象信息。"""
        return self._test_object_info
