"""
认证管理模块

本模块为认证功能的聚合入口，负责将认证相关的子模块统一注册到同一路由前缀下。

路由前缀: /auth
标签: 认证管理

子模块概览:
    - auth_endpoints: 认证端点（登录、注册、验证码、当前用户信息）
    - auth_deps: 认证依赖项（JWT令牌校验、项目权限校验）

导出依赖项:
    - get_current_user: 获取当前登录用户（用于其他模块的权限依赖注入）
    - require_project_owner: 校验当前用户是否为项目所有者
    - ProjectAccessChecker: 项目权限校验器（可复用的权限检查类）
    - oauth2_scheme: OAuth2密码模式令牌提取器
"""
from fastapi import APIRouter
from app.api.v1.endpoints.auth_endpoints import router as endpoints_router
from app.api.v1.endpoints.auth_deps import (
    get_current_user,
    require_project_owner,
    ProjectAccessChecker,
    oauth2_scheme,
)

__all__ = [
    "get_current_user",
    "require_project_owner",
    "ProjectAccessChecker",
    "oauth2_scheme",
]

# 认证管理路由，前缀 /auth，包含登录/注册/验证码等端点
router = APIRouter(prefix="/auth", tags=["认证管理"])
# 将认证端点子路由注册到当前路由下
router.include_router(endpoints_router)
