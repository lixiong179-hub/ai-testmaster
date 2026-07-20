"""
需求链接CRUD端点模块

路由前缀: /requirement-link（由父模块注册）
标签: 需求链接

端点: POST /, GET /list/{project_id}, GET /{link_id}, PUT /{link_id}, DELETE /{link_id}
权限: Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.requirement_link import RequirementLink
from app.schemas.requirement_link import (
    RequirementLinkCreate,
    RequirementLinkUpdate,
    RequirementLinkResponse,
    RequirementLinkListResponse,
    AuthConfigResponse,
    AuthTypeEnum,
)
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.utils.db_time import utcnow
from loguru import logger

router = APIRouter()


async def _verify_project_permission(
    db: AsyncSession, project_id: int, user_id: int
) -> None:
    """验证用户对项目的操作权限，不存在或无权限时抛403。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目",
        )


async def _get_owned_link(
    db: AsyncSession, link_id: int, user_id: int
) -> RequirementLink:
    """查询链接并验证用户对所属项目的权限，不存在抛404、无权限抛403。"""
    result = await db.execute(
        select(RequirementLink).where(RequirementLink.id == link_id)
    )
    link = result.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="需求链接不存在",
        )
    await _verify_project_permission(db, link.project_id, user_id)
    return link


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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        await _verify_project_permission(db, link_data.project_id, current_user.id)

        exists_result = await db.execute(
            select(RequirementLink).where(
                RequirementLink.project_id == link_data.project_id,
                RequirementLink.link_url == link_data.link_url,
            )
        )
        if exists_result.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该链接已存在",
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

        link = RequirementLink(
            project_id=link_data.project_id,
            link_name=link_data.link_name,
            link_type=link_data.link_type.value,
            link_url=link_data.link_url,
            created_by=current_user.id,
            auth_type=link_data.auth_type.value,
            description=link_data.description,
            cache_expire_minutes=link_data.cache_expire_minutes,
        )
        link.auth_config = auth_config
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return _build_link_response(link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建需求链接失败",
        )


@router.get("/list/{project_id}", response_model=RequirementLinkListResponse)
async def get_requirement_links(
    project_id: int,
    link_type: Optional[str] = Query(None, description="链接类型筛选"),
    is_active: Optional[bool] = Query(None, description="是否启用筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        await _verify_project_permission(db, project_id, current_user.id)
        skip = (page - 1) * page_size

        conditions = [
            RequirementLink.project_id == project_id,
            Project.user_id == current_user.id,
        ]
        if link_type:
            conditions.append(RequirementLink.link_type == link_type)
        if is_active is not None:
            conditions.append(RequirementLink.is_active == is_active)

        links_result = await db.execute(
            select(RequirementLink).join(Project).where(*conditions)
            .order_by(RequirementLink.create_time.desc())
            .offset(skip).limit(page_size)
        )
        links = links_result.scalars().all()

        count_result = await db.execute(
            select(func.count()).select_from(RequirementLink).join(Project).where(*conditions)
        )
        total = count_result.scalar() or 0

        return RequirementLinkListResponse(
            total=total,
            items=[_build_link_response(link) for link in links],
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取需求链接列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取需求链接列表失败",
        )


@router.get("/{link_id}", response_model=RequirementLinkResponse)
async def get_requirement_link_detail(
    link_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        link = await _get_owned_link(db, link_id, current_user.id)
        return _build_link_response(link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取需求链接详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取需求链接详情失败",
        )


@router.put("/{link_id}", response_model=RequirementLinkResponse)
async def update_requirement_link(
    link_id: int,
    link_data: RequirementLinkUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        link = await _get_owned_link(db, link_id, current_user.id)

        update_data = link_data.model_dump(exclude_unset=True)
        auth_fields = ['username', 'password', 'token', 'api_key', 'api_key_header', 'cookie']
        if any(k in update_data for k in auth_fields):
            auth_config = dict(link.auth_config) if link.auth_config else {}
            for field in auth_fields:
                if update_data.get(field) is not None:
                    auth_config[field] = update_data.pop(field)
            update_data['auth_config'] = auth_config
        for field in auth_fields:
            update_data.pop(field, None)
        if 'link_type' in update_data and update_data['link_type']:
            update_data['link_type'] = update_data['link_type'].value
        if 'auth_type' in update_data and update_data['auth_type']:
            update_data['auth_type'] = update_data['auth_type'].value

        protected_fields = {'id', 'project_id', 'created_by', 'create_time'}
        for key, value in update_data.items():
            if key not in protected_fields and hasattr(link, key):
                setattr(link, key, value)
        link.update_time = utcnow()
        await db.commit()
        await db.refresh(link)
        return _build_link_response(link)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新需求链接失败",
        )


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement_link(
    link_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        link = await _get_owned_link(db, link_id, current_user.id)
        await db.delete(link)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除需求链接失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除需求链接失败",
        )
