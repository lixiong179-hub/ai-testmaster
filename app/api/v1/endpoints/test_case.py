"""
测试用例管理模块（聚合入口）

本模块为测试用例功能的聚合入口，将用例相关的所有子模块统一注册到同一路由前缀下。

路由前缀: /testCase
标签: 测试用例管理

子模块概览:
    - test_case_crud: 用例基础CRUD（创建/查询/更新/删除）
    - test_case_crud_batch: 用例批量操作（批量恢复/批量删除）
    - test_case_workflow: 用例工作流与纠正状态管理
    - test_case_status: 用例状态相关接口
    - test_case_version: 用例版本管理与导出
    - test_case_ai: AI生成测试用例（非流式）
    - test_case_ai_stream: AI流式生成测试用例

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.test_case_crud import router as crud_router
from app.api.v1.endpoints.test_case_crud_batch import router as crud_batch_router
from app.api.v1.endpoints.test_case_workflow import router as workflow_router
from app.api.v1.endpoints.test_case_status import router as status_router
from app.api.v1.endpoints.test_case_version import router as version_router
from app.api.v1.endpoints.test_case_ai import router as ai_router
from app.api.v1.endpoints.test_case_ai_stream import router as ai_stream_router
from app.api.v1.endpoints.test_case_lineage import router as lineage_router

# 测试用例管理路由，包含CRUD、工作流、版本、AI生成等子模块
router = APIRouter(prefix="/testCase", tags=["测试用例管理"])

# 注册各子模块路由
router.include_router(crud_router)
router.include_router(crud_batch_router)
router.include_router(workflow_router)
router.include_router(status_router)
router.include_router(version_router)
router.include_router(ai_router)
router.include_router(ai_stream_router)
router.include_router(lineage_router)
