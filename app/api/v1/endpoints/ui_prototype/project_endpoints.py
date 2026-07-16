"""
UI原型项目端点模块（thin wrapper）

本模块定义UI原型项目级管理的API端点，包括原型上传、列表查询和删除。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - POST   /projects/{project_id}/upload  - 上传原型文件
    - GET    /projects/{project_id}/list     - 获取项目原型列表
    - DELETE /projects/{project_id}/{prototype_id} - 删除原型

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 支持上传HTML/PDF/图片等原型文件
    - 上传后自动创建页面记录

router 定义保留在此文件中；路由处理函数与工具函数拆分至:
    - _project_endpoints_helpers.py  纯辅助函数（流程摘要/序列化）
    - _project_endpoints_routes.py   项目CRUD路由处理函数
    - _project_endpoints_flow.py     流程数据路由处理函数

公开符号通过本文件 re-export，保持 import 路径不变。
"""
from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.api.v1.endpoints.ui_prototype._project_endpoints_helpers import (
    _build_flow_summary,
    _count_navigation_edges,
    _serialize_project_flow_data,
)
from app.api.v1.endpoints.ui_prototype._project_endpoints_routes import (
    create_prototype_project,
    delete_prototype_project,
    get_prototype_projects,
)
from app.api.v1.endpoints.ui_prototype._project_endpoints_flow import (
    get_flow_data,
    save_flow_data,
)

router = APIRouter(tags=["UI原型管理"])

router.add_api_route(
    "/project",
    create_prototype_project,
    methods=["POST"],
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/project/list/{project_id}",
    get_prototype_projects,
    methods=["GET"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/project/{prototype_project_id}",
    delete_prototype_project,
    methods=["DELETE"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/flow/{project_id}",
    save_flow_data,
    methods=["PUT"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/flow/{project_id}",
    get_flow_data,
    methods=["GET"],
    response_model=ApiResponse,
)

__all__ = [
    "router",
    "_count_navigation_edges",
    "_build_flow_summary",
    "_serialize_project_flow_data",
    "create_prototype_project",
    "get_prototype_projects",
    "delete_prototype_project",
    "save_flow_data",
    "get_flow_data",
]
