"""
文件管理模块（聚合入口）

本模块为文件功能的聚合入口，将文件相关的子模块统一注册到同一路由前缀下。

路由前缀: /file
标签: 文件管理

子模块概览:
    - file_upload: 单文件上传
    - file_batch_upload: 批量文件上传
    - file_management: 文件管理（列表/详情/删除）
    - file_export: 文件导出

所有端点均需要Bearer令牌认证。
"""
from fastapi import APIRouter

from app.api.v1.endpoints.file_upload import router as upload_router
from app.api.v1.endpoints.file_management import router as management_router
from app.api.v1.endpoints.file_export import router as export_router
from app.api.v1.endpoints.file_batch_upload import router as batch_upload_router

router = APIRouter(prefix="/file", tags=["文件管理"])

router.include_router(upload_router)
router.include_router(management_router)
router.include_router(export_router)
router.include_router(batch_upload_router)
