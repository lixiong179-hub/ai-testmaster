from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.test_capability import (
    TestCapabilityCreate,
    TestCapabilityResponse,
    TestCapabilityUpdate,
)
from app.services.test_capability_service import (
    DuplicateCapabilityKeyError,
    _UNSET,
    create_capability,
    delete_capability,
    get_capability_by_id,
    get_capabilities_by_project,
    update_capability,
)

router = APIRouter(prefix="/test-capability", tags=["测试能力管理"])


@router.get("/", response_model=ApiResponse)
async def list_capabilities(
    project_id: int = Query(..., description="项目ID"),
    status: Optional[str] = Query(None, description="能力状态过滤"),
    include_archived: bool = Query(False, description="是否包含已归档能力"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    def _list(sync_db):
        capabilities = get_capabilities_by_project(
            sync_db, project_id=project_id, status=status, include_archived=include_archived,
        )
        total = len(capabilities)
        skip = (page - 1) * page_size
        page_capabilities = capabilities[skip:skip + page_size]
        items = [
            TestCapabilityResponse.model_validate(c).model_dump(mode="json")
            for c in page_capabilities
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    data = await db.run_sync(_list)
    return create_response(data=data)


@router.post("/", response_model=TestCapabilityResponse, status_code=status.HTTP_201_CREATED)
async def create_capability_endpoint(
    data: TestCapabilityCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _create(sync_db):
        return create_capability(
            sync_db,
            project_id=data.project_id,
            key=data.key,
            title=data.title,
            description=data.description,
            status=data.status,
        )
    try:
        capability = await db.run_sync(_create)
    except DuplicateCapabilityKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    return capability


@router.get("/{capability_id}", response_model=TestCapabilityResponse)
async def get_capability_endpoint(
    capability_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get(sync_db):
        return get_capability_by_id(sync_db, capability_id=capability_id)
    capability = await db.run_sync(_get)
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return capability


@router.put("/{capability_id}", response_model=TestCapabilityResponse)
async def update_capability_endpoint(
    capability_id: int,
    data: TestCapabilityUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    update_kwargs = {}
    for field_name in ("key", "title", "description", "status"):
        value = getattr(data, field_name, None)
        update_kwargs[field_name] = value if value is not None else _UNSET

    def _update(sync_db):
        return update_capability(sync_db, capability_id=capability_id, **update_kwargs)
    try:
        capability = await db.run_sync(_update)
    except DuplicateCapabilityKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return capability


@router.delete("/{capability_id}", response_model=TestCapabilityResponse)
async def delete_capability_endpoint(
    capability_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除能力：将 status 置为 archived，返回更新后的能力对象。"""
    def _delete(sync_db):
        return delete_capability(
            sync_db, capability_id=capability_id, actor_id=current_user.id,
        )
    capability = await db.run_sync(_delete)
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return capability
