from typing import List, Any
"""
用户管理端点模块

本模块定义用户管理的API端点，提供用户信息的查询和更新功能。

路由前缀: /user
标签: 用户管理

端点概览:
    - GET  /me          - 获取当前用户信息
    - PUT  /me          - 更新当前用户信息
    - PUT  /me/password - 修改密码

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 用户信息包括用户名、邮箱、创建时间等
    - 修改密码需验证旧密码
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
from app.schemas.user import (
    User, UserCreate, UserUpdate, UserWithRoles,
    Role, RoleCreate, RoleUpdate,
    Permission, PermissionCreate, PermissionUpdate,
    Token,
)
from app.services.user_service import (
    UserService, RoleService, PermissionService, UserRoleService,
)
from app.api.v1.endpoints.auth import get_current_user
from app.utils.jwt_utils import create_access_token
from app.core.config import settings
from loguru import logger

router = APIRouter(prefix="/user", tags=["用户管理"])


def _require_superuser(current_user: User) -> User:
    """要求当前用户为超级管理员"""
    if not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要超级管理员权限"
        )
    return current_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(async_get_db)
) -> Token:
    """用户登录 - 使用JWT令牌"""
    def _authenticate(sync_db):
        return UserService.authenticate_user(
            sync_db, form_data.username, form_data.password
        )
    user = await db.run_sync(_authenticate)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db)
) -> dict[str, Any]:
    """获取当前登录用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": getattr(current_user, 'phone', None),
        "is_superuser": getattr(current_user, 'is_superuser', False),
    }


@router.post("/", response_model=User)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """创建用户（需认证）"""
    def _create(sync_db):
        return UserService.create_user(sync_db, user_in)
    user = await db.run_sync(_create)
    logger.info(f"用户 {current_user.username} 创建了新用户 {user.username}")
    return user


@router.get("/", response_model=List[User])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> List[User]:
    """获取用户列表（需认证）"""
    def _list(sync_db):
        return UserService.get_users(sync_db, skip=skip, limit=limit)
    users = await db.run_sync(_list)
    return users


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


@router.delete("/role/{role_id}", response_model=dict)
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


@router.post("/permission", response_model=Permission)
async def create_permission(
    permission_in: PermissionCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """创建权限（需超级管理员）"""
    _require_superuser(current_user)
    def _create(sync_db):
        return PermissionService.create_permission(sync_db, permission_in)
    permission = await db.run_sync(_create)
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
    def _list(sync_db):
        return PermissionService.get_permissions(sync_db, skip=skip, limit=limit)
    permissions = await db.run_sync(_list)
    return permissions


@router.get("/permission/{perm_id}", response_model=Permission)
async def get_permission(
    perm_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """获取权限详情（需认证）"""
    def _get(sync_db):
        return PermissionService.get_permission_by_id(sync_db, perm_id)
    permission = await db.run_sync(_get)
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
    def _update(sync_db):
        return PermissionService.update_permission(sync_db, perm_id, permission_in)
    permission = await db.run_sync(_update)
    logger.info(f"管理员 {current_user.username} 更新了权限 ID={perm_id}")
    return permission


@router.delete("/permission/{perm_id}", response_model=dict)
async def delete_permission(
    perm_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除权限（需超级管理员）"""
    _require_superuser(current_user)
    def _delete(sync_db):
        return PermissionService.delete_permission(sync_db, perm_id)
    await db.run_sync(_delete)
    logger.warning(f"管理员 {current_user.username} 删除了权限 ID={perm_id}")
    return {"message": "权限删除成功"}


@router.post("/role/assign", response_model=dict)
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


@router.post("/role/remove", response_model=dict)
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


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> UserWithRoles:
    """获取用户详情（需认证）"""
    def _get_with_roles(sync_db):
        user = UserService.get_user_by_id(sync_db, user_id)
        if not user:
            return None
        roles = UserRoleService.get_user_roles(sync_db, user.id)
        user_dict = user.__dict__
        user_dict["roles"] = roles
        return user_dict
    user_dict = await db.run_sync(_get_with_roles)
    if user_dict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return UserWithRoles(**user_dict)


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """更新用户信息（需认证，仅自己或管理员可操作）"""
    if user_id != current_user.id and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的信息或需要管理员权限"
        )
    def _update(sync_db):
        return UserService.update_user(sync_db, user_id, user_in)
    user = await db.run_sync(_update)
    logger.info(f"用户 {current_user.username} 更新了用户 ID={user_id} 的信息")
    return user


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除用户（需超级管理员）"""
    _require_superuser(current_user)
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    def _delete(sync_db):
        return UserService.delete_user(sync_db, user_id)
    await db.run_sync(_delete)
    logger.warning(f"管理员 {current_user.username} 删除了用户 ID={user_id}")
    return {"message": "用户删除成功"}
