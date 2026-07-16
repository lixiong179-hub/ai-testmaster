"""
项目配置端点模块

本模块定义项目配置和被测对象管理的API端点，包括环境配置读写和被测对象信息管理。

路由前缀: /project（由父模块project.py注册）
标签: 项目管理

端点概览:
    - GET  /{project_id}/config        - 获取项目配置
    - PUT  /{project_id}/config        - 更新项目配置
    - GET  /{project_id}/test-object   - 获取被测对象信息
    - PUT  /{project_id}/test-object   - 更新被测对象信息

权限要求: 所有端点需要Bearer令牌认证，且仅能操作当前用户拥有的项目

业务说明:
    - Web环境密码在读取时脱敏，写入时自动加密
    - 被测对象信息与Web环境配置关联存储
    - 设备配置以JSON格式存储
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.schemas.project import TestObjectInfoUpdate, ProjectConfigUpdate
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.utils.crypto import encrypt_password, mask_password
from app.core.exception import create_response
from loguru import logger
import json

router = APIRouter()


def _parse_web_env_configs(project: Project) -> dict | None:
    """
    解析项目的Web环境配置，密码字段脱敏

    从数据库中读取JSON格式的Web环境配置，解析后对密码字段进行脱敏处理。

    Args:
        project: 项目ORM对象

    Returns:
        dict | None: 脱敏后的环境配置字典，解析失败返回None
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


def _parse_device_config(project: Project) -> dict | None:
    """
    解析项目的设备配置

    Args:
        project: 项目ORM对象

    Returns:
        dict | None: 设备配置字典，解析失败返回None
    """
    if not project.device_config:
        return None
    try:
        if isinstance(project.device_config, dict):
            return dict(project.device_config)
        return json.loads(project.device_config)
    except (TypeError, json.JSONDecodeError):
        return None


@router.get("/{project_id}/config", response_model=dict)
async def get_project_config(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目配置

    获取指定项目的类型、Web环境配置和设备配置。密码字段脱敏返回。

    路径参数:
        - project_id: 项目ID

    响应格式:
        - project_type: 项目类型
        - web_env_configs: Web环境配置（密码脱敏）
        - device_config: 设备配置

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        return create_response(
            data={
                "project_type": project.project_type,
                "web_env_configs": _parse_web_env_configs(project),
                "device_config": _parse_device_config(project)
            },
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取项目配置失败")


@router.put("/{project_id}/config", response_model=dict)
async def update_project_config(
    project_id: int,
    config_data: ProjectConfigUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新项目配置

    更新指定项目的类型、Web环境配置和/或设备配置。
    Web环境密码在写入时自动加密，仅加密非已加密的密码字段。

    路径参数:
        - project_id: 项目ID

    请求参数(ProjectConfigUpdate):
        - project_type: 项目类型（可选）
        - web_env_configs: Web环境配置（可选）
        - device_config: 设备配置（可选）

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        if config_data.project_type is not None:
            project.project_type = config_data.project_type
        if config_data.web_env_configs is not None:
            web_configs_input = config_data.web_env_configs.model_dump(exclude_none=True)
            if web_configs_input:
                existing_configs = {}
                if project.web_env_configs:
                    try:
                        existing_configs = json.loads(project.web_env_configs)
                    except json.JSONDecodeError:
                        pass
                for env_name in ['test', 'staging', 'prod']:
                    if env_name in web_configs_input and web_configs_input[env_name]:
                        env_data = web_configs_input[env_name].copy() if isinstance(web_configs_input[env_name], dict) else web_configs_input[env_name]
                        password = env_data.get('password') if isinstance(env_data, dict) else None
                        if password and not password.startswith('gAAAAA'):
                            env_data['password'] = encrypt_password(password)
                        existing_configs[env_name] = env_data
                project.web_env_configs = json.dumps(existing_configs)
            else:
                project.web_env_configs = None
        if config_data.device_config is not None:
            device_config = config_data.device_config.model_dump(exclude_none=True)
            if device_config:
                project.device_config = json.dumps(device_config)
            else:
                project.device_config = None
        await db.commit()
        await db.refresh(project)
        return create_response(
            data={
                "project_type": project.project_type,
                "web_env_configs": _parse_web_env_configs(project),
                "device_config": _parse_device_config(project)
            },
            msg="更新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新项目配置失败: {e}")
        raise HTTPException(status_code=500, detail="更新项目配置失败，请检查参数")


@router.get("/{project_id}/test-object", response_model=dict)
async def get_test_object(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取被测对象信息

    获取指定项目的被测对象信息，包括项目类型、测试环境URL/用户名/密码和设备信息。

    路径参数:
        - project_id: 项目ID

    响应格式:
        - type: 项目类型
        - url/username/password: 测试环境连接信息
        - device_info: 设备配置信息

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        # 从Web环境配置中提取测试环境信息
        web_env = None
        if project.web_env_configs:
            try:
                if isinstance(project.web_env_configs, dict):
                    configs = project.web_env_configs
                else:
                    configs = json.loads(project.web_env_configs)
                test_cfg = configs.get('test', {})
                if test_cfg:
                    web_env = {
                        "url": test_cfg.get('url'),
                        "username": test_cfg.get('username'),
                        "password": mask_password(test_cfg['password']) if test_cfg.get('password') else None
                    }
            except (TypeError, json.JSONDecodeError, KeyError):
                pass
        return create_response(
            data={
                "type": project.project_type,
                "url": web_env.get('url') if web_env else None,
                "username": web_env.get('username') if web_env else None,
                "password": web_env.get('password') if web_env else None,
                "device_info": _parse_device_config(project)
            },
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取被测对象失败: {e}")
        raise HTTPException(status_code=500, detail="获取被测对象失败")


@router.put("/{project_id}/test-object", response_model=dict)
async def update_test_object(
    project_id: int,
    obj_data: TestObjectInfoUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新被测对象信息

    更新指定项目的被测对象信息，支持更新项目类型、测试环境连接信息和设备配置。
    密码字段自动加密存储。

    路径参数:
        - project_id: 项目ID

    请求参数(TestObjectInfoUpdate):
        - type: 项目类型
        - url/username/password: 测试环境连接信息
        - device_info: 设备配置
        - app_package/app_activity: App包名和Activity

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        if obj_data.type:
            project.project_type = obj_data.type
        # 合并已有Web环境配置
        existing_configs = {}
        if project.web_env_configs:
            try:
                if isinstance(project.web_env_configs, dict):
                    existing_configs = dict(project.web_env_configs)
                else:
                    existing_configs = json.loads(project.web_env_configs)
            except (TypeError, json.JSONDecodeError):
                pass
        # 更新测试环境连接信息
        if obj_data.url or obj_data.username or obj_data.password:
            test_cfg = existing_configs.get('test', {})
            if obj_data.url:
                test_cfg['url'] = obj_data.url
            if obj_data.username:
                test_cfg['username'] = obj_data.username
            if obj_data.password:
                password = obj_data.password
                # 仅加密非已加密的密码
                if not password.startswith('gAAAAA'):
                    password = encrypt_password(password)
                test_cfg['password'] = password
            existing_configs['test'] = test_cfg
            project.web_env_configs = json.dumps(existing_configs)
        # 更新设备配置
        if obj_data.device_info:
            project.device_config = json.dumps(obj_data.device_info)
        # 更新App包名（合并到设备配置中）
        if obj_data.app_package:
            dev_cfg = _parse_device_config(project) or {}
            dev_cfg['app_package'] = obj_data.app_package
            project.device_config = json.dumps(dev_cfg)
        # 更新App Activity（合并到设备配置中）
        if obj_data.app_activity:
            dev_cfg = _parse_device_config(project) or {}
            dev_cfg['app_activity'] = obj_data.app_activity
            project.device_config = json.dumps(dev_cfg)
        await db.commit()
        await db.refresh(project)
        return create_response(data={"id": project.id}, msg="更新成功")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新被测对象失败: {e}")
        raise HTTPException(status_code=500, detail="更新被测对象失败")
