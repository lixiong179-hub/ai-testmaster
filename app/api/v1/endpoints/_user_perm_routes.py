"""用户权限管理端点子模块。

从 user.py 拆分，提供权限 CRUD 端点。

路由前缀: /user/permission（由父模块 user.py 通过 include_router 注册）
标签: 用户管理

端点概览:
    - POST   /permission             - 创建权限（需超级管理员）
    - GET    /permission             - 获取权限列表
    - GET    /permission/{perm_id}   - 获取权限详情
    - PUT    /permission/{perm_id}   - 更新权限（需超级管理员）
    - DELETE /permission/{perm_id}   - 删除权限（需超级管理员）

权限要求: 所有端点需要Bearer令牌认证
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db
from app.schemas.common import ApiResponse
from app.schemas.user import Permission, PermissionCreate, PermissionUpdate
from app.services.user_service import PermissionService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.api.v1.endpoints.user import _require_superuser

router = APIRouter()


@router.post("/permission", response_model=Permission)
async def create_permission(
    permission_in: PermissionCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """创建权限（需超级管理员）"""
    _require_superuser(current_user)
    service = PermissionService(db)
    permission = await service.create_permission_async(permission_in)
    logger.info(f"管理员 {current_user.username} 创建了权限 {permission.name}")
    return permission


@router.get("/permission", response_model=List[Permission])
async def get_permissions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> List[Permission]:
    """获取权限列表（需认证）"""
    service = PermissionService(db)
    permissions = await service.get_permissions_async(skip=skip, limit=limit)
    return permissions


@router.get("/permission/{perm_id}", response_model=Permission)
async def get_permission(
    perm_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """获取权限详情（需认证）"""
    service = PermissionService(db)
    permission = await service.get_permission_by_id_async(perm_id)
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限不存在"
        )
    return permission


@router.put("/permission/{perm_id}", response_model=Permission)
async def update_permission(
    perm_id: int,
    permission_in: PermissionUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """更新权限（需超级管理员）"""
    _require_superuser(current_user)
    service = PermissionService(db)
    permission = await service.update_permission_async(perm_id, permission_in)
    logger.info(f"管理员 {current_user.username} 更新了权限 ID={perm_id}")
    return permission


@router.delete("/permission/{perm_id}", response_model=ApiResponse)
async def delete_permission(
    perm_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除权限（需超级管理员）"""
    _require_superuser(current_user)
    service = PermissionService(db)
    await service.delete_permission_async(perm_id)
    logger.warning(f"管理员 {current_user.username} 删除了权限 ID={perm_id}")
    return {"message": "权限删除成功"}
