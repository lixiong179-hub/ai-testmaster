"""
需求链接管理模块（聚合入口）

本模块为需求链接功能的聚合入口，将需求链接相关的子模块统一注册到同一路由前缀下。

路由前缀: /requirement-link
标签: 需求链接管理

子模块概览:
    - requirement_link_crud: 增删改查端点（创建/列表/详情/更新/删除）
    - requirement_link_fetch: 内容获取端点（获取内容/验证链接）

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.requirement_link_crud import router as crud_router
from app.api.v1.endpoints.requirement_link_fetch import router as fetch_router

router = APIRouter(prefix="/requirement-link", tags=["需求链接管理"])

# 注册子模块路由
router.include_router(crud_router)
router.include_router(fetch_router)
