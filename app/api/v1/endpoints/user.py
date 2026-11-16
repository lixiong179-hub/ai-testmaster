from typing import Any
"""
用户管理端点模块

本模块定义用户管理的API端点，提供用户认证、用户CRUD功能，
以及角色管理（CRUD + 分配/移除）与权限管理（CRUD）端点
（原 _user_role_routes / _user_perm_routes 已内联回本模块）。

路由前缀: /user
标签: 用户管理

端点概览:
    - POST /login          - 用户登录（JWT令牌）
    - GET  /me             - 获取当前用户信息
    - POST /               - 创建用户
    - GET  /               - 获取用户列表
    - GET  /{user_id}      - 获取用户详情（含角色）
    - PUT  /{user_id}      - 更新用户信息
    - DELETE /{user_id}    - 删除用户

子模块（通过 include_router 注册）:
    - _user_role_routes  : 角色CRUD + 分配/移除
    - _user_perm_routes  : 权限CRUD

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.user import (
    User, UserCreate, UserUpdate, UserWithRoles,
    Token, Role, RoleCreate, RoleUpdate,
    Permission, PermissionCreate, PermissionUpdate,
)
from app.services.user_service import (
    UserService, UserRoleService, RoleService, PermissionService,
)
# R4-7：依赖实现已下沉至 app.api.v1.endpoints._deps，
# 打破 `user ↔ _user_perm_routes/_user_role_routes` 的循环导入；此处保留同名绑定。
from app.api.v1.endpoints._deps import _require_superuser
from app.api.v1.endpoints.auth import get_current_user
from app.utils.jwt_utils import create_access_token
from app.core.config import settings
from loguru import logger

router = APIRouter(prefix="/user", tags=["用户管理"])


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Token:
    """用户登录 - 使用JWT令牌"""
    user = await UserService(db).authenticate_user_async(
        form_data.username, form_data.password
    )
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
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """创建用户（需认证）"""
    user = await UserService(db).create_user_async(user_in)
    logger.info(f"用户 {current_user.username} 创建了新用户 {user.username}")
    return user


@router.get("/", response_model=list[User])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[User]:
    """获取用户列表（需认证）"""
    users = await UserService(db).get_users_async(skip=skip, limit=limit)
    return users


# 角色与权限端点内联注册（原 _user_role_routes / _user_perm_routes 已合并，
# 位置保持在 /{user_id} 路由之前，避免路径参数误匹配）
@router.post("/role", response_model=Role)
async def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """创建角色（需超级管理员）"""
    _require_superuser(current_user)
    service = RoleService(db)
    role = await service.create_role_async(role_in)
    logger.info(f"管理员 {current_user.username} 创建了角色 {role.name}")
    return role


@router.get("/role", response_model=list[Role])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[Role]:
    """获取角色列表（需认证）"""
    service = RoleService(db)
    roles = await service.get_roles_async(skip=skip, limit=limit)
    return roles


@router.get("/role/{role_id}", response_model=Role)
async def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """获取角色详情（需认证）"""
    service = RoleService(db)
    role = await service.get_role_by_id_async(role_id)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Role:
    """更新角色（需超级管理员）"""
    _require_superuser(current_user)
    service = RoleService(db)
    role = await service.update_role_async(role_id, role_in)
    logger.info(f"管理员 {current_user.username} 更新了角色 ID={role_id}")
    return role


@router.delete("/role/{role_id}", response_model=ApiResponse)
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除角色（需超级管理员）"""
    _require_superuser(current_user)
    service = RoleService(db)
    await service.delete_role_async(role_id)
    logger.warning(f"管理员 {current_user.username} 删除了角色 ID={role_id}")
    return {"message": "角色删除成功"}


@router.post("/role/assign", response_model=ApiResponse)
async def assign_role(
    user_id: int = Body(...),
    role_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """分配角色给用户（需超级管理员）"""
    _require_superuser(current_user)
    service = UserRoleService(db)
    await service.assign_role_async(user_id, role_id)
    logger.info(f"管理员 {current_user.username} 为用户 ID={user_id} 分配了角色 ID={role_id}")
    return {"message": "角色分配成功"}


@router.post("/role/remove", response_model=ApiResponse)
async def remove_role(
    user_id: int = Body(...),
    role_id: int = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """移除用户角色（需超级管理员）"""
    _require_superuser(current_user)
    service = UserRoleService(db)
    await service.remove_role_async(user_id, role_id)
    logger.info(f"管理员 {current_user.username} 移除了用户 ID={user_id} 的角色 ID={role_id}")
    return {"message": "角色移除成功"}


@router.post("/permission", response_model=Permission)
async def create_permission(
    permission_in: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Permission:
    """创建权限（需超级管理员）"""
    _require_superuser(current_user)
    service = PermissionService(db)
    permission = await service.create_permission_async(permission_in)
    logger.info(f"管理员 {current_user.username} 创建了权限 {permission.name}")
    return permission


@router.get("/permission", response_model=list[Permission])
async def get_permissions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> list[Permission]:
    """获取权限列表（需认证）"""
    service = PermissionService(db)
    permissions = await service.get_permissions_async(skip=skip, limit=limit)
    return permissions


@router.get("/permission/{perm_id}", response_model=Permission)
async def get_permission(
    perm_id: int,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除权限（需超级管理员）"""
    _require_superuser(current_user)
    service = PermissionService(db)
    await service.delete_permission_async(perm_id)
    logger.warning(f"管理员 {current_user.username} 删除了权限 ID={perm_id}")
    return {"message": "权限删除成功"}


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> UserWithRoles:
    """获取用户详情（需认证）"""
    user = await UserService(db).get_user_by_id_async(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    roles = await UserRoleService(db).get_user_roles_async(user.id)
    user_dict = user.__dict__
    user_dict["roles"] = roles
    return UserWithRoles(**user_dict)


@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """更新用户信息（需认证，仅自己或管理员可操作）"""
    if user_id != current_user.id and not getattr(current_user, 'is_superuser', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的信息或需要管理员权限"
        )
    user = await UserService(db).update_user_async(user_id, user_in)
    logger.info(f"用户 {current_user.username} 更新了用户 ID={user_id} 的信息")
    return user


@router.delete("/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """删除用户（需超级管理员）"""
    _require_superuser(current_user)
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账号"
        )
    await UserService(db).delete_user_async(user_id)
    logger.warning(f"管理员 {current_user.username} 删除了用户 ID={user_id}")
    return {"message": "用户删除成功"}
