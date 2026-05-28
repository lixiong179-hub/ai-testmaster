"""
项目核心CRUD端点模块

本模块定义项目的核心增删改查API端点，包括项目创建、列表查询、详情获取和删除。

路由前缀: /project（由父模块project.py注册）
标签: 项目管理

端点概览:
    - POST   /               - 创建项目
    - GET    /list            - 获取项目列表（分页）
    - GET    /{project_id}    - 获取项目详情
    - DELETE /{project_id}    - 删除项目

权限要求: 所有端点需要Bearer令牌认证，且仅能操作当前用户拥有的项目

业务说明:
    - 创建项目时支持配置Web环境（test/staging/prod）和设备配置
    - 项目详情包含关联文件列表，Web环境密码脱敏返回
    - 删除为物理删除，会永久移除项目数据
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.project import (
    ProjectCreate,
)
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.crud.file import get_project_files
from app.utils.crypto import encrypt_password, mask_password
from app.core.exception import create_response
from loguru import logger
import json

router = APIRouter()


class SelfTestScheduleRequest(BaseModel):
    schedule: str | None = None


@router.post("/", response_model=dict)
@router.post("/create", response_model=dict)
async def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建项目

    创建新项目，支持配置Web环境参数和设备信息。
    Web环境密码自动加密存储，项目初始状态为1（活跃）。

    请求参数(ProjectCreate):
        - name: 项目名称（必填，需唯一）
        - description: 项目描述
        - project_type: 项目类型（web/app等）
        - web_env_configs: Web环境配置（test/staging/prod）
        - device_config: 设备配置

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 400: 项目名称已存在
        HTTPException 500: 创建失败
    """
    try:
        # 校验项目名称唯一性
        if db.query(Project).filter(Project.name == project.name).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目名称已存在"
            )
        new_project = Project(
            name=project.name,
            description=project.description,
            user_id=current_user.id,
            status=1,
            project_type=project.project_type
        )
        # 处理Web环境配置，密码字段加密存储
        if project.web_env_configs:
            web_configs = {}
            for env_name in ['test', 'staging', 'prod']:
                env_config = getattr(project.web_env_configs, env_name, None)
                if env_config and env_config.password:
                    web_configs[env_name] = {
                        "url": env_config.url,
                        "username": env_config.username,
                        "password": encrypt_password(env_config.password)
                    }
                elif env_config:
                    web_configs[env_name] = {
                        "url": env_config.url,
                        "username": env_config.username,
                        "password": None
                    }
            if web_configs:
                new_project.web_env_configs = json.dumps(web_configs)
        # 处理设备配置，序列化为JSON存储
        if project.device_config:
            new_project.device_config = json.dumps(project.device_config.model_dump(exclude_none=True))
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return create_response(
            data={
                "project_id": new_project.id,
                "name": new_project.name,
                "description": new_project.description,
                "project_type": new_project.project_type,
                "create_time": new_project.create_time
            },
            msg="创建成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建项目失败: {e}")
        raise HTTPException(status_code=500, detail="创建项目失败")


@router.get("/list", response_model=dict)
async def get_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=1000, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目列表

    分页查询当前用户拥有的所有项目，按创建时间排序。

    请求参数:
        - page: 页码（默认1）
        - page_size: 每页数量（默认10，最大1000）

    响应格式:
        - items: 项目列表
        - total: 总数
        - page/page_size: 分页信息

    权限要求: 需要Bearer令牌认证
    """
    try:
        offset = (page - 1) * page_size
        # 仅查询当前用户拥有的项目，实现数据隔离
        projects = db.query(Project).filter(Project.user_id == current_user.id).offset(offset).limit(page_size).all()
        total = db.query(Project).filter(Project.user_id == current_user.id).count()
        project_list = [{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "project_type": p.project_type,
            "status": p.status,
            "create_time": p.create_time
        } for p in projects]
        return create_response(
            data={"items": project_list, "total": total, "page": page, "page_size": page_size},
            msg="获取成功"
        )
    except Exception as e:
        logger.error(f"获取项目列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取项目列表失败")


@router.get("/{project_id}", response_model=dict)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目详情

    查询指定项目的完整信息，包括关联文件列表、Web环境配置和设备配置。
    Web环境密码字段脱敏后返回，不暴露原始密码。

    路径参数:
        - project_id: 项目ID

    响应格式:
        - 项目基本信息 + files列表 + web_env_configs + device_config

    权限要求: 需要Bearer令牌认证，且仅能查看自己拥有的项目

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        # 获取项目关联的文件列表
        files = get_project_files(db, project_id)
        file_list = [{
            "id": f.id, "file_name": f.file_name, "file_type": f.file_type,
            "file_url": f.file_url, "file_source": f.file_source,
            "size": f.size, "upload_time": f.upload_time
        } for f in files]
        # 解析Web环境配置，密码字段脱敏
        web_env_configs = None
        if project.web_env_configs:
            try:
                web_env_configs = json.loads(project.web_env_configs)
                for env_name in ['test', 'staging', 'prod']:
                    if env_name in web_env_configs and web_env_configs[env_name].get('password'):
                        web_env_configs[env_name]['password'] = mask_password(web_env_configs[env_name]['password'])
            except json.JSONDecodeError:
                web_env_configs = None
        # 解析设备配置
        device_config = None
        if project.device_config:
            try:
                device_config = json.loads(project.device_config)
            except json.JSONDecodeError:
                device_config = None
        return create_response(
            data={
                "id": project.id, "name": project.name, "description": project.description,
                "project_type": project.project_type, "status": project.status,
                "create_time": project.create_time, "update_time": project.update_time,
                "files": file_list, "web_env_configs": web_env_configs, "device_config": device_config
            },
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目详情失败: {e}")
        raise HTTPException(status_code=500, detail="获取项目详情失败")


def _delete_project_core_assets(db: Session, project_id: int) -> None:
    """删除项目核心资产，避免数据库未启用级联时项目物理删除失败。"""
    from app.models.test_case import TestCase
    from app.models.test_result import TestResult
    from app.models.test_task import TestTask

    db.query(TestResult).filter(TestResult.project_id == project_id).delete(synchronize_session=False)

    for task in db.query(TestTask).filter(TestTask.project_id == project_id).all():
        db.delete(task)

    for test_case in db.query(TestCase).filter(TestCase.project_id == project_id).all():
        db.delete(test_case)


@router.delete("/{project_id}", response_model=dict)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除项目

    物理删除指定项目及其所有数据。此操作不可逆。

    路径参数:
        - project_id: 项目ID

    权限要求: 需要Bearer令牌认证，且仅能删除自己拥有的项目

    Raises:
        HTTPException 403: 无权限操作此项目
    """
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
        if getattr(project, "is_self_test", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="自测项目不可删除")
        _delete_project_core_assets(db, project_id)
        db.delete(project)
        db.commit()
        return create_response(data={}, msg="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除项目失败: {e}")
        raise HTTPException(status_code=500, detail="删除项目失败")


@router.put("/{project_id}/self-test-schedule", response_model=dict)
async def update_self_test_schedule(
    project_id: int,
    body: SelfTestScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not project.is_self_test:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅自测项目可配置定时计划")

    if body.schedule:
        from app.tasks.self_test_scheduler import validate_cron_expression

        if not validate_cron_expression(body.schedule):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的cron表达式")

    project.self_test_schedule = body.schedule
    db.commit()
    db.refresh(project)

    return create_response(
        data={"project_id": project.id, "self_test_schedule": project.self_test_schedule},
        msg="更新成功",
    )
