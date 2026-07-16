"""
执行可视化API - 聚合入口

本模块为执行可视化功能的聚合入口，将可视化相关的子模块统一注册到同一路由前缀下。

路由前缀: /execution-vis
标签: 测试执行

子模块概览:
    - execution_vis_config: 可视化配置端点
    - execution_vis_video_replay: 视频管理与回放控制端点

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter

from app.api.v1.endpoints.execution_vis_config import router as config_router
from app.api.v1.endpoints.execution_vis_video_replay import router as video_replay_router

router = APIRouter(prefix="/execution-vis", tags=["测试执行"])

# 注册子模块路由
router.include_router(config_router)
router.include_router(video_replay_router)
