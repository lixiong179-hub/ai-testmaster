"""
运行时特性开关端点模块（已迁移至 AsyncSession）

提供特性开关的 CRUD 与启用/禁用切换接口。

路由前缀: （由 main.py 统一添加 /api/v1/feature-flags）
标签: 特性开关

端点概览:
    - GET    /                    — 列表
    - POST   /                    — 创建
    - PUT    /{key}               — 更新
    - DELETE /{key}               — 删除
    - POST   /{key}/toggle        — 启用/禁用

迁移说明（任务1 续作 - endpoint + service 全链路 async 试点）:
    本模块与 FeatureFlagService 一并迁移，验证 endpoint → service → AsyncSession
    全链路异步模式。改造要点:
        1. db: Session → db: AsyncSession，依赖 get_db → async_get_db
        2. service.list_flags() → await service.list_flags()（service 方法已改 async）
        3. _require_admin 保持 async，依赖 get_current_user 不变
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
)
from app.services.feature_flag_service import FeatureFlagService


async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not any(r.name == "admin" for r in current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


router = APIRouter(tags=["特性开关"])


@router.get("/", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeatureFlagResponse]:
    """获取所有特性开关列表"""
    service = FeatureFlagService(db)
    return await service.list_flags()


@router.post("/", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    data: FeatureFlagCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(_require_admin),
) -> FeatureFlagResponse:
    """创建特性开关"""
    service = FeatureFlagService(db)
    try:
        flag = await service.create_flag(
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
async def update_feature_flag(
    key: str,
    data: FeatureFlagUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(_require_admin),
) -> FeatureFlagResponse:
    """更新特性开关"""
    service = FeatureFlagService(db)
    update_kwargs = data.model_dump(exclude_unset=True)
    try:
        flag = await service.update_flag(key, **update_kwargs)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return flag


@router.delete("/{key}", response_model=dict)
async def delete_feature_flag(
    key: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(_require_admin),
) -> Dict[str, Any]:
    """删除特性开关"""
    service = FeatureFlagService(db)
    try:
        await service.delete_flag(key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return create_response(msg=f"特性开关已删除: {key}")


@router.post("/{key}/toggle", response_model=FeatureFlagResponse)
async def toggle_feature_flag(
    key: str,
    enabled: bool,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(_require_admin),
) -> FeatureFlagResponse:
    """启用/禁用特性开关"""
    service = FeatureFlagService(db)
    try:
        flag = await service.toggle_flag(key, enabled=enabled)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return flag
