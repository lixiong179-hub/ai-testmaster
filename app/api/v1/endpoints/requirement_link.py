"""
Requirement Link API - 需求链接和UI原型图链接管理接口
"""
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.utils.db_time import utcnow

from app.db.database import get_db
from app.schemas.requirement_link import (
    RequirementLinkCreate,
    RequirementLinkUpdate,
    RequirementLinkResponse,
    RequirementLinkDetailResponse,
    RequirementLinkListRequest,
    RequirementLinkListResponse,
    AuthConfigResponse,
    FetchContentRequest,
    FetchContentResponse,
    AuthTypeEnum,
    LinkTypeEnum
)
from app.models.user import User
from app.models.project import Project
from app.models.test_point import TestPoint
from app.api.v1.endpoints.auth import get_current_user
from app.crud import requirement_link as requirement_link_crud
from app.services.link_fetcher_service import link_fetcher_service
from loguru import logger
router = APIRouter()



def _build_auth_config_response(auth_type: str, auth_config: Optional[dict]) -> Optional[AuthConfigResponse]:
    """构建脱敏的认证配置响应"""
    if not auth_config:
        return AuthConfigResponse(auth_type=auth_type, has_credentials=False)

    has_credentials = False
    if auth_type == "basic":
        has_credentials = bool(auth_config.get("username") and auth_config.get("password"))
    elif auth_type in ["bearer", "api_key"]:
        has_credentials = bool(auth_config.get("token") or auth_config.get("api_key"))
    elif auth_type == "cookie":
        has_credentials = bool(auth_config.get("cookie"))

    return AuthConfigResponse(auth_type=auth_type, has_credentials=has_credentials)


def _build_link_response(link) -> RequirementLinkResponse:
    """构建需求链接响应"""
    return RequirementLinkResponse(
        id=link.id,
        project_id=link.project_id,
        link_name=link.link_name,
        link_type=link.link_type,
        link_url=link.link_url,
        auth_type=link.auth_type,
        auth_config=_build_auth_config_response(link.auth_type, link.auth_config),
        description=link.description,
        is_active=link.is_active,
        last_fetch_time=link.last_fetch_time,
        last_fetch_status=link.last_fetch_status,
        cached_content=link.cached_content[:500] if link.cached_content else None,  # 只返回前500字符预览
        cache_expire_minutes=link.cache_expire_minutes,
        created_by=link.created_by,
        create_time=link.create_time,
        update_time=link.update_time
    )


@router.post("", response_model=RequirementLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_requirement_link(
    link_data: RequirementLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建需求链接

    支持多种认证类型：
    - none: 无认证
    - basic: Basic Auth (需要提供用户名和密码)
    - bearer: Bearer Token
    - api_key: API Key (需要提供Key和Header名称)
    - cookie: Cookie认证
    """
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == link_data.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 检查链接是否已存在
        if requirement_link_crud.check_link_exists(db, link_data.project_id, link_data.link_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该链接已存在"
            )

        # 构建认证配置
        auth_config = None
        if link_data.auth_type != AuthTypeEnum.NONE:
            auth_config = {}
            if link_data.auth_type == AuthTypeEnum.BASIC:
                auth_config = {"username": link_data.username, "password": link_data.password}
            elif link_data.auth_type == AuthTypeEnum.BEARER:
                auth_config = {"token": link_data.token}
            elif link_data.auth_type == AuthTypeEnum.API_KEY:
                auth_config = {"api_key": link_data.api_key, "api_key_header": link_data.api_key_header or "X-API-Key"}
            elif link_data.auth_type == AuthTypeEnum.COOKIE:
                auth_config = {"cookie": link_data.cookie}

        # 创建链接
        link = requirement_link_crud.create_requirement_link(
            db=db,
            project_id=link_data.project_id,
            link_name=link_data.link_name,
            link_type=link_data.link_type.value,
            link_url=link_data.link_url,
            created_by=current_user.id,
            auth_type=link_data.auth_type.value,
            auth_config=auth_config,
            description=link_data.description,
            cache_expire_minutes=link_data.cache_expire_minutes
        )

        return _build_link_response(link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建需求链接失败: {str(e)}"
        )


@router.get("/list/{project_id}", response_model=RequirementLinkListResponse)
async def get_requirement_links(
    project_id: int,
    link_type: Optional[str] = Query(None, description="链接类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否启用筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目的需求链接列表
    """
    try:
        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 获取列表
        skip = (page - 1) * page_size
        links = requirement_link_crud.get_requirement_links_by_project(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            link_type=link_type,
            is_active=is_active,
            skip=skip,
            limit=page_size
        )

        # 获取总数
        total = requirement_link_crud.get_requirement_links_count(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            link_type=link_type,
            is_active=is_active
        )

        return RequirementLinkListResponse(
            total=total,
            items=[_build_link_response(link) for link in links],
            page=page,
            page_size=page_size
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取需求链接列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取需求链接列表失败: {str(e)}"
        )


@router.get("/{link_id}", response_model=RequirementLinkResponse)
async def get_requirement_link_detail(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取需求链接详情
    """
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )

        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        return _build_link_response(link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取需求链接详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取需求链接详情失败: {str(e)}"
        )


@router.put("/{link_id}", response_model=RequirementLinkResponse)
async def update_requirement_link(
    link_id: int,
    link_data: RequirementLinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新需求链接
    """
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )

        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 构建更新数据
        update_data = link_data.model_dump(exclude_unset=True)

        # 处理认证配置更新
        if any(k in update_data for k in ['username', 'password', 'token', 'api_key', 'cookie']):
            auth_config = dict(link.auth_config) if link.auth_config else {}

            if update_data.get('username') is not None:
                auth_config['username'] = update_data.pop('username')
            if update_data.get('password') is not None:
                auth_config['password'] = update_data.pop('password')
            if update_data.get('token') is not None:
                auth_config['token'] = update_data.pop('token')
            if update_data.get('api_key') is not None:
                auth_config['api_key'] = update_data.pop('api_key')
            if update_data.get('api_key_header') is not None:
                auth_config['api_key_header'] = update_data.pop('api_key_header')
            if update_data.get('cookie') is not None:
                auth_config['cookie'] = update_data.pop('cookie')

            update_data['auth_config'] = auth_config

        # 删除不需要的字段
        update_data.pop('username', None)
        update_data.pop('password', None)
        update_data.pop('token', None)
        update_data.pop('api_key', None)
        update_data.pop('api_key_header', None)
        update_data.pop('cookie', None)

        # 转换枚举值
        if 'link_type' in update_data and update_data['link_type']:
            update_data['link_type'] = update_data['link_type'].value
        if 'auth_type' in update_data and update_data['auth_type']:
            update_data['auth_type'] = update_data['auth_type'].value

        # 更新
        updated_link = requirement_link_crud.update_requirement_link(
            db=db,
            link_id=link_id,
            **update_data
        )

        return _build_link_response(updated_link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新需求链接失败: {str(e)}"
        )


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除需求链接
    """
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )

        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        requirement_link_crud.delete_requirement_link(db, link_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除需求链接失败: {str(e)}"
        )


@router.post("/fetch-content", response_model=FetchContentResponse)
async def fetch_link_content(
    request: FetchContentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取需求链接内容（带认证）

    支持缓存，缓存过期后自动重新获取
    """
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, request.link_id)

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )

        # 验证项目权限
        project = db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 检查缓存是否有效
        cached = False
        if not request.force_refresh and link.cached_content and link.last_fetch_time:
            expire_time = link.last_fetch_time + timedelta(minutes=link.cache_expire_minutes)
            if utcnow() < expire_time:
                cached = True
                return FetchContentResponse(
                    success=True,
                    content=link.cached_content,
                    content_type="cached",
                    message="从缓存获取成功",
                    cached=True
                )

        # 获取新内容
        if link.link_type == "ui_mockup":
            success, result, message = link_fetcher_service.fetch_and_parse_ui_mockup(
                url=link.link_url,
                auth_type=link.auth_type,
                auth_config=link.auth_config
            )

            if success:
                content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                requirement_link_crud.update_link_cache(db, link.id, content, "success")
                return FetchContentResponse(
                    success=True,
                    content=content,
                    content_type="json",
                    message="获取成功",
                    cached=False
                )
            else:
                requirement_link_crud.update_link_cache(db, link.id, "", "failed")
                return FetchContentResponse(
                    success=False,
                    content=None,
                    content_type=None,
                    message=message,
                    cached=False
                )
        else:
            success, content, message = link_fetcher_service.fetch_content(
                url=link.link_url,
                auth_type=link.auth_type,
                auth_config=link.auth_config
            )

            if success:
                requirement_link_crud.update_link_cache(db, link.id, content, "success")
                return FetchContentResponse(
                    success=True,
                    content=content,
                    content_type=message,
                    message="获取成功",
                    cached=False
                )
            else:
                requirement_link_crud.update_link_cache(db, link.id, "", "failed")
                return FetchContentResponse(
                    success=False,
                    content=None,
                    content_type=None,
                    message=message,
                    cached=False
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取链接内容失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取链接内容失败: {str(e)}"
        )


@router.post("/validate")
async def validate_link_access(
    link_url: str,
    auth_type: str = Query("none", description="认证类型"),
    username: Optional[str] = Query(None, description="用户名"),
    password: Optional[str] = Query(None, description="密码"),
    token: Optional[str] = Query(None, description="Token"),
    api_key: Optional[str] = Query(None, description="API Key"),
    api_key_header: Optional[str] = Query(None, description="API Key Header"),
    cookie: Optional[str] = Query(None, description="Cookie"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    验证链接是否可访问（用于配置时的测试）
    """
    try:
        # 构建认证配置
        auth_config = None
        if auth_type != "none":
            auth_config = {}
            if auth_type == "basic":
                auth_config = {"username": username, "password": password}
            elif auth_type == "bearer":
                auth_config = {"token": token}
            elif auth_type == "api_key":
                auth_config = {"api_key": api_key, "api_key_header": api_key_header or "X-API-Key"}
            elif auth_type == "cookie":
                auth_config = {"cookie": cookie}

        # 验证访问
        success, message = link_fetcher_service.validate_link_access(
            url=link_url,
            auth_type=auth_type,
            auth_config=auth_config
        )

        return {
            "success": success,
            "message": message,
            "link_url": link_url,
            "auth_type": auth_type
        }

    except Exception as e:
        logger.error(f"验证链接失败: {e}")
        return {
            "success": False,
            "message": f"验证失败: {str(e)}",
            "link_url": link_url,
            "auth_type": auth_type
        }



