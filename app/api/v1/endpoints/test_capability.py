from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.enums import CapabilityStatus
from app.models.test_capability import TestCapability
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.test_capability import (
    TestCapabilityCreate,
    TestCapabilityResponse,
    TestCapabilityUpdate,
)
from app.services.test_capability_service import delete_capability

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
    conditions = [TestCapability.project_id == project_id]
    if not include_archived:
        conditions.append(TestCapability.status != CapabilityStatus.ARCHIVED.value)
    if status is not None:
        conditions.append(TestCapability.status == status)

    result = await db.execute(
        select(TestCapability).where(*conditions).order_by(TestCapability.key)
    )
    capabilities: List[TestCapability] = list(result.scalars().all())

    total = len(capabilities)
    skip = (page - 1) * page_size
    page_capabilities = capabilities[skip:skip + page_size]
    items = [
        TestCapabilityResponse.model_validate(c).model_dump(mode="json")
        for c in page_capabilities
    ]
    return create_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/", response_model=TestCapabilityResponse, status_code=status.HTTP_201_CREATED)
async def create_capability_endpoint(
    data: TestCapabilityCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    capability = TestCapability(
        project_id=data.project_id,
        key=data.key,
        title=data.title,
        description=data.description,
        status=data.status,
    )
    db.add(capability)
    try:
        await db.flush()
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Capability key '{data.key}' already exists in project {data.project_id}",
        ) from e
    await db.refresh(capability)
    return capability


@router.get("/{capability_id}", response_model=TestCapabilityResponse)
async def get_capability_endpoint(
    capability_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TestCapability).where(TestCapability.id == capability_id)
    )
    capability = result.scalars().first()
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
    result = await db.execute(
        select(TestCapability).where(TestCapability.id == capability_id)
    )
    capability = result.scalars().first()
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )

    for field_name in ("key", "title", "description", "status"):
        value = getattr(data, field_name, None)
        if value is not None and hasattr(capability, field_name):
            setattr(capability, field_name, value)

    try:
        await db.flush()
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Capability key conflict after update",
        ) from e
    await db.refresh(capability)
    return capability


@router.delete("/{capability_id}", response_model=TestCapabilityResponse)
async def delete_capability_endpoint(
    capability_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除能力：将 status 置为 archived，返回更新后的能力对象。

    使用 db.run_sync 包装深层 sync 链
    (delete_capability → transition_capability → _write_capability_audit_log →
    audit_service.log_action)，保证 sync 操作与 AsyncSession 共享事务。
    """
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
