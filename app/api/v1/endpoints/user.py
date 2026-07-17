from typing import List, Any
"""
用户管理端点模块

本模块定义用户管理的API端点，提供用户认证、用户CRUD功能。
角色管理和权限管理端点已拆分至 _user_role_routes 和 _user_perm_routes。

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
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
from app.schemas.common import ApiResponse
from app.schemas.user import (
    User, UserCreate, UserUpdate, UserWithRoles,
    Token,
)
from app.services.user_service import (
    UserService, UserRoleService,
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
    user = await UserService(db).create_user_async(user_in)
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
    users = await UserService(db).get_users_async(skip=skip, limit=limit)
    return users


# 注册角色和权限子模块路由（在 /{user_id} 路由之前，避免路径参数误匹配）
from app.api.v1.endpoints._user_role_routes import router as role_router
from app.api.v1.endpoints._user_perm_routes import router as perm_router

router.include_router(role_router)
router.include_router(perm_router)


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(async_get_db),
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
    db: AsyncSession = Depends(async_get_db),
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
    await UserService(db).delete_user_async(user_id)
    logger.warning(f"管理员 {current_user.username} 删除了用户 ID={user_id}")
    return {"message": "用户删除成功"}
