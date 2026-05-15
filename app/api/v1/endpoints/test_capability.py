from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
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


@router.get("/", response_model=List[TestCapabilityResponse])
def list_capabilities(
    project_id: int = Query(..., description="项目ID"),
    status: Optional[str] = Query(None, description="能力状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    capabilities = get_capabilities_by_project(db, project_id=project_id, status=status)
    return capabilities


@router.post("/", response_model=TestCapabilityResponse, status_code=status.HTTP_201_CREATED)
def create_capability_endpoint(
    data: TestCapabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        capability = create_capability(
            db,
            project_id=data.project_id,
            key=data.key,
            title=data.title,
            description=data.description,
            status=data.status,
        )
    except DuplicateCapabilityKeyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    return capability


@router.get("/{capability_id}", response_model=TestCapabilityResponse)
def get_capability_endpoint(
    capability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    capability = get_capability_by_id(db, capability_id=capability_id)
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return capability


@router.put("/{capability_id}", response_model=TestCapabilityResponse)
def update_capability_endpoint(
    capability_id: int,
    data: TestCapabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_kwargs = {}
    for field_name in ("key", "title", "description", "status"):
        value = getattr(data, field_name, None)
        update_kwargs[field_name] = value if value is not None else _UNSET
    try:
        capability = update_capability(db, capability_id=capability_id, **update_kwargs)
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


@router.delete("/{capability_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_capability_endpoint(
    capability_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = delete_capability(db, capability_id=capability_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability {capability_id} not found",
        )
    return None
