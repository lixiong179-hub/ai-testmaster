"""
需求链接CRUD端点模块

本模块定义需求链接的增删改查API端点，管理测试用例与需求之间的关联关系。

路由前缀: /requirement-link（由父模块requirement_link.py注册）
标签: 需求链接

端点概览:
    - POST   /                          - 创建需求链接
    - GET    /list                      - 获取需求链接列表
    - GET    /{link_id}                 - 获取链接详情
    - DELETE /{link_id}                 - 删除需求链接

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 需求链接建立测试用例与需求条目的关联
    - 支持一对多关联（一个需求关联多个用例）
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session
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
from app.api.v1.endpoints.auth import get_current_user
from app.crud import requirement_link as requirement_link_crud
from loguru import logger

router = APIRouter()


def _build_auth_config_response(auth_type: str, auth_config: Optional[dict]) -> Optional[AuthConfigResponse]:
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
        cached_content=link.cached_content[:500] if link.cached_content else None,
        cache_expire_minutes=link.cache_expire_minutes,
        created_by=link.created_by,
        create_time=link.create_time,
        update_time=link.update_time
    )


@router.post("/", response_model=RequirementLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_requirement_link(
    link_data: RequirementLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        project = db.query(Project).filter(
            Project.id == link_data.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        if requirement_link_crud.check_link_exists(db, link_data.project_id, link_data.link_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该链接已存在"
            )
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
    try:
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
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
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )
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
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )
        project = db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        update_data = link_data.model_dump(exclude_unset=True)
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
        update_data.pop('username', None)
        update_data.pop('password', None)
        update_data.pop('token', None)
        update_data.pop('api_key', None)
        update_data.pop('api_key_header', None)
        update_data.pop('cookie', None)
        if 'link_type' in update_data and update_data['link_type']:
            update_data['link_type'] = update_data['link_type'].value
        if 'auth_type' in update_data and update_data['auth_type']:
            update_data['auth_type'] = update_data['auth_type'].value
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
    try:
        link = requirement_link_crud.get_requirement_link_by_id(db, link_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )
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
