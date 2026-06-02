"""
运行时特性开关端点模块

提供特性开关的 CRUD 与启用/禁用切换接口。

路由前缀: （由 main.py 统一添加 /api/v1/feature-flags）
标签: 特性开关

端点概览:
    - GET    /                    — 列表
    - POST   /                    — 创建
    - PUT    /{key}               — 更新
    - DELETE /{key}               — 删除
    - POST   /{key}/toggle        — 启用/禁用
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import get_db
from app.models.user import User
from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
)
from app.services.feature_flag_service import FeatureFlagService

router = APIRouter(tags=["特性开关"])


@router.get("/", response_model=List[FeatureFlagResponse])
def list_feature_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeatureFlagResponse]:
    """获取所有特性开关列表"""
    service = FeatureFlagService(db)
    return service.list_flags()


@router.post("/", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
def create_feature_flag(
    data: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureFlagResponse:
    """创建特性开关"""
    service = FeatureFlagService(db)
    try:
        flag = service.create_flag(
            key=data.key,
            name=data.name,
            description=data.description,
            enabled=data.enabled,
            rollout_percentage=data.rollout_percentage,
            target_type=data.target_type,
            target_project_ids=data.target_project_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return flag


@router.put("/{key}", response_model=FeatureFlagResponse)
def update_feature_flag(
    key: str,
    data: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureFlagResponse:
    """更新特性开关属性"""
    service = FeatureFlagService(db)
    update_kwargs = data.model_dump(exclude_unset=True)
    try:
        flag = service.update_flag(key, **update_kwargs)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return flag


@router.delete("/{key}", response_model=dict)
def delete_feature_flag(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """删除特性开关"""
    service = FeatureFlagService(db)
    try:
        service.delete_flag(key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return create_response(msg=f"特性开关已删除: {key}")


@router.post("/{key}/toggle", response_model=FeatureFlagResponse)
def toggle_feature_flag(
    key: str,
    enabled: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureFlagResponse:
    """切换特性开关启用/禁用状态"""
    service = FeatureFlagService(db)
    try:
        flag = service.toggle_flag(key, enabled=enabled)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return flag
