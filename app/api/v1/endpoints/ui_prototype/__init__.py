"""
UI原型管理子包

本包定义UI原型管理的所有API端点，包括项目级管理、页面级管理和原型解析。

路由前缀: /ui-prototype
标签: UI原型管理

子模块概览:
    - project_endpoints: 项目级原型管理（上传/列表/删除）
    - screen_endpoints: 页面级原型管理（页面CRUD/元素标注）
    - parse_endpoints: 原型解析（AI解析页面结构/元素识别）
    - helpers: 共享工具函数（上传目录管理/响应构建）

导出:
    - router: 聚合路由器
    - UPLOAD_DIR: 上传目录路径
    - _ensure_upload_dir: 确保上传目录存在
    - _build_screen_response: 构建页面响应数据
"""
from fastapi import APIRouter

from app.api.v1.endpoints.ui_prototype.project_endpoints import router as project_router
from app.api.v1.endpoints.ui_prototype.screen_endpoints import router as screen_router
from app.api.v1.endpoints.ui_prototype.screen_endpoints_manage import router as screen_manage_router
from app.api.v1.endpoints.ui_prototype.parse_endpoints import router as parse_router
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR, _ensure_upload_dir, _build_screen_response

router: APIRouter = APIRouter(prefix="/ui-prototype", tags=["UI原型管理"])

router.include_router(project_router)
router.include_router(screen_router)
router.include_router(screen_manage_router)
router.include_router(parse_router)

__all__: list[str] = [
    'router',
    'UPLOAD_DIR',
    '_ensure_upload_dir',
    '_build_screen_response',
]
