"""
测试执行模块（聚合入口）

本模块为测试执行功能的聚合入口，将执行相关的子模块统一注册到同一路由前缀下。

路由前缀: /execution
标签: 测试执行

子模块概览:
    - execution_core: 执行核心（启动/停止/状态查询/回放会话/失败分析）
    - execution_management: 执行管理（截图/视频查询）

注意：回放控制（开始/暂停/恢复/停止/跳转）和可视化配置由 execution_visualization 模块提供，
该模块独立注册在同一路由前缀下。

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.execution_core import router as core_router
from app.api.v1.endpoints.execution_management import router as management_router

router = APIRouter(prefix="/execution", tags=["测试执行"])

router.include_router(core_router)
router.include_router(management_router)
