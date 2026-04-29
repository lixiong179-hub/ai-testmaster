"""
项目管理模块（聚合入口）

本模块为项目功能的聚合入口，将项目核心CRUD和配置管理子模块统一注册到同一路由前缀下。

路由前缀: /project
标签: 项目管理

子模块概览:
    - project_core: 项目核心CRUD（创建/列表/详情/删除）
    - project_config: 项目配置与被测对象管理

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.project_core import router as core_router
from app.api.v1.endpoints.project_config import router as config_router

# 项目管理路由，包含核心CRUD和配置管理两个子路由
router = APIRouter(prefix="/project", tags=["项目管理"])
# 注册项目核心端点（创建、列表、详情、删除）
router.include_router(core_router)
# 注册项目配置端点（环境配置、被测对象信息）
router.include_router(config_router)
