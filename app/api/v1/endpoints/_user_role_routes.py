"""用户角色管理端点子模块。

从 user.py 拆分，提供角色 CRUD 及角色分配/移除端点。

路由前缀: /user/role（由父模块 user.py 通过 include_router 注册）
标签: 用户管理

端点概览:
    - POST   /role             - 创建角色（需超级管理员）
    - GET    /role             - 获取角色列表
    - GET    /role/{role_id}   - 获取角色详情
    - PUT    /role/{role_id}   - 更新角色（需超级管理员）
    - DELETE /role/{role_id}   - 删除角色（需超级管理员）
    - POST   /role/assign      - 分配角色给用户（需超级管理员）
    - POST   /role/remove      - 移除用户角色（需超级管理员）

权限要求: 所有端点需要Bearer令牌认证
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db
from app.schemas.common import ApiResponse
from app.schemas.user import Role, RoleCreate, RoleUpdate
from app.services.user_service import RoleService, UserRoleService
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.api.v1.endpoints.user import _require_superuser

router = APIRouter()


@router.post("/role", response_model=Role)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """创建角色（需超级管理员）"""
    _require_superuser(current_user)
    def _create(sync_db):
        return RoleService.create_role(sync_db, role_in)
    role = await db.run_sync(_create)
    logger.info(f"管理员 {current_user.username} 创建了角色 {role.name}")
    return role


@router.get("/role", response_model=List[Role])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> List[Role]:
    """获取角色列表（需认证）"""
    def _list(sync_db):
        return RoleService.get_roles(sync_db, skip=skip, limit=limit)
    roles = await db.run_sync(_list)
    return roles


@router.get("/role/{role_id}", response_model=Role)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """获取角色详情（需认证）"""
    def _get(sync_db):
        return RoleService.get_role_by_id(sync_db, role_id)
    role = await db.run_sync(_get)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    return role


@router.put("/role/{role_id}", response_model=Role)
async def update_role(
    role_id: int,
    role_in: RoleUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """更新角色（需超级管理员）"""
    _require_superuser(current_user)
    def _update(sync_db):
        return RoleService.update_role(sync_db, role_id, role_in)
    role = await db.run_sync(_update)
    logger.info(f"管理员 {current_user.username} 更新了角色 ID={role_id}")
    return role


@router.delete("/role/{role_id}", response_model=ApiResponse)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除角色（需超级管理员）"""
    _require_superuser(current_user)
    def _delete(sync_db):
        return RoleService.delete_role(sync_db, role_id)
    await db.run_sync(_delete)
    logger.warning(f"管理员 {current_user.username} 删除了角色 ID={role_id}")
    return {"message": "角色删除成功"}


@router.post("/role/assign", response_model=ApiResponse)
async def assign_role(
    user_id: int = Body(...),
    role_id: int = Body(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """分配角色给用户（需超级管理员）"""
    _require_superuser(current_user)
    def _assign(sync_db):
        return UserRoleService.assign_role(sync_db, user_id, role_id)
    await db.run_sync(_assign)
    logger.info(f"管理员 {current_user.username} 为用户 ID={user_id} 分配了角色 ID={role_id}")
    return {"message": "角色分配成功"}


@router.post("/role/remove", response_model=ApiResponse)
async def remove_role(
    user_id: int = Body(...),
    role_id: int = Body(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """移除用户角色（需超级管理员）"""
    _require_superuser(current_user)
    def _remove(sync_db):
        return UserRoleService.remove_role(sync_db, user_id, role_id)
    await db.run_sync(_remove)
    logger.info(f"管理员 {current_user.username} 移除了用户 ID={user_id} 的角色 ID={role_id}")
    return {"message": "角色移除成功"}
