"""
测试执行模块（聚合入口）

本模块为测试执行功能的聚合入口，将执行相关的子模块统一注册到同一路由前缀下。

路由前缀: /execution
标签: 测试执行

子模块概览:
    - execution_core: 执行核心（启动/停止/状态查询）
    - execution_management: 执行管理（列表/详情/删除）
    - execution_replay: 执行回放（步骤回放/视频回放）
    - execution_visualization: 执行可视化（实时监控/截图查看）
    - execution_vis_config: 可视化配置
    - execution_vis_schemas: 可视化数据Schema
    - execution_vis_video_replay: 视频回放

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter
from app.api.v1.endpoints.execution_core import router as core_router
from app.api.v1.endpoints.execution_management import router as management_router
from app.api.v1.endpoints.execution_replay import router as replay_router

router = APIRouter(prefix="/execution", tags=["测试执行"])

router.include_router(core_router)
router.include_router(management_router)
router.include_router(replay_router)
