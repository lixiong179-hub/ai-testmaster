"""
测试点管理模块（聚合入口）

本模块为测试点功能的聚合入口，将测试点相关的子模块统一注册到同一路由前缀下。

路由前缀: /test-point
标签: 测试点管理

子模块概览:
    - test_point_query: 查询端点（分析/列表/详情/提取）
    - test_point_mutate: 变更端点（批量保存/更新/删除）
    - test_point_import: XMind导入端点（导入/预览）

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.test_point_query import router as query_router
from app.api.v1.endpoints.test_point_mutate import router as mutate_router
from app.api.v1.endpoints.test_point_import import router as import_router
from app.api.v1.endpoints.test_point_management import router as management_router

router = APIRouter(prefix="/test-point", tags=["测试点管理"])

router.include_router(query_router)
router.include_router(mutate_router)
router.include_router(import_router)
router.include_router(management_router)
