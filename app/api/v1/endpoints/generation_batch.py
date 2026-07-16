"""generation_batch 端点 thin wrapper。

router 定义保留在此文件中；路由处理函数与工具函数拆分至：
    - _generation_batch_helpers.py  常量与纯工具函数
    - _generation_batch_routes.py   CRUD 路由处理函数
    - _generation_batch_save.py     save 路由处理函数及私有辅助

公开符号通过本文件 re-export，保持 import 路径不变。
"""
from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.api.v1.endpoints._generation_batch_helpers import (
    VALID_TRANSITIONS,
    _batch_to_response,
    _create_case_version_snapshot,
    _deprecate_case,
    _generate_batch_no,
    _validate_status_transition,
)
from app.api.v1.endpoints._generation_batch_routes import (
    create_generation_batch,
    get_generation_batch,
    update_generation_batch,
)
from app.api.v1.endpoints._generation_batch_save import save_generation_batch

router = APIRouter(tags=["生成批次"])

router.add_api_route(
    "", create_generation_batch, methods=["POST"], response_model=ApiResponse
)
router.add_api_route(
    "/{batch_id}", get_generation_batch, methods=["GET"], response_model=ApiResponse
)
router.add_api_route(
    "/{batch_id}", update_generation_batch, methods=["PATCH"], response_model=ApiResponse
)
router.add_api_route(
    "/{batch_id}/save", save_generation_batch, methods=["POST"], response_model=ApiResponse
)

__all__ = [
    "router",
    "VALID_TRANSITIONS",
    "_validate_status_transition",
    "_generate_batch_no",
    "_batch_to_response",
    "_create_case_version_snapshot",
    "_deprecate_case",
    "create_generation_batch",
    "get_generation_batch",
    "update_generation_batch",
    "save_generation_batch",
]
