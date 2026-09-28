"""项目配置端点的共享 helper 函数。

从 project_config.py 拆出，封装 Web 环境配置和设备配置的解析与合并逻辑，
便于独立测试与复用。
"""
import json
from typing import Any, Dict, Optional

from app.models.project import Project
from app.utils.crypto import encrypt_password, mask_password


def _parse_web_env_configs(project: Project) -> Optional[dict]:
    """解析项目的 Web 环境配置，密码字段脱敏。

    Args:
        project: 项目 ORM 对象

    Returns:
        脱敏后的环境配置字典，解析失败返回 None
    """
    if not project.web_env_configs:
        return None
    try:
        if isinstance(project.web_env_configs, dict):
            configs = dict(project.web_env_configs)
        else:
            configs = json.loads(project.web_env_configs)
        for env_name in ['test', 'staging', 'prod']:
            if env_name in configs and configs[env_name].get('password'):
                configs[env_name]['password'] = mask_password(configs[env_name]['password'])
        return configs
    except (TypeError, json.JSONDecodeError):
        return None


def _parse_device_config(project: Project) -> Optional[dict]:
    """解析项目的设备配置。

    Args:
        project: 项目 ORM 对象

    Returns:
        设备配置字典，解析失败返回 None
    """
    if not project.device_config:
        return None
    try:
        if isinstance(project.device_config, dict):
            return dict(project.device_config)
        return json.loads(project.device_config)
    except (TypeError, json.JSONDecodeError):
        return None


def _merge_web_env_configs_for_update(
    project: Project,
    web_configs_input: Dict[str, Any],
) -> Optional[str]:
    """合并更新请求中的 web_env_configs 到项目已有配置。

    用于 update_project_config 端点：对每个环境的密码字段，
    若非已加密形式（gAAAAA 前缀）则自动加密。

    Args:
        project: 项目 ORM 对象
        web_configs_input: 待合并的环境配置字典（已 exclude_none）

    Returns:
        合并后的 JSON 字符串；若输入为空则返回 None
    """
    if not web_configs_input:
        return None
    existing_configs: Dict[str, Any] = {}
    if project.web_env_configs:
        try:
            existing_configs = json.loads(project.web_env_configs)
        except json.JSONDecodeError:
            pass
    for env_name in ['test', 'staging', 'prod']:
        if env_name in web_configs_input and web_configs_input[env_name]:
            env_data = (
                web_configs_input[env_name].copy()
                if isinstance(web_configs_input[env_name], dict)
                else web_configs_input[env_name]
            )
            password = env_data.get('password') if isinstance(env_data, dict) else None
            if password and not password.startswith('gAAAAA'):
                env_data['password'] = encrypt_password(password)
            existing_configs[env_name] = env_data
    return json.dumps(existing_configs)


def _merge_test_env_for_update(
    project: Project,
    url: Optional[str],
    username: Optional[str],
    password: Optional[str],
) -> Optional[str]:
    """合并测试环境连接信息到项目 web_env_configs。

    用于 update_test_object 端点：仅当 url/username/password 至少一项非空时触发。
    密码若非已加密形式则自动加密。

    Args:
        project: 项目 ORM 对象
        url: 测试环境 URL（可选）
        username: 用户名（可选）
        password: 密码（可选）

    Returns:
        更新后的 web_env_configs JSON 字符串；若无更新则返回原值。
    """
    existing_configs: Dict[str, Any] = {}
    if project.web_env_configs:
        try:
            if isinstance(project.web_env_configs, dict):
                existing_configs = dict(project.web_env_configs)
            else:
                existing_configs = json.loads(project.web_env_configs)
        except (TypeError, json.JSONDecodeError):
            pass
    test_cfg = existing_configs.get('test', {})
    if url:
        test_cfg['url'] = url
    if username:
        test_cfg['username'] = username
    if password:
        if not password.startswith('gAAAAA'):
            password = encrypt_password(password)
        test_cfg['password'] = password
    existing_configs['test'] = test_cfg
    return json.dumps(existing_configs)


__all__ = [
    "_parse_web_env_configs",
    "_parse_device_config",
    "_merge_web_env_configs_for_update",
    "_merge_test_env_for_update",
]
