"""Pipeline 反推摘要、信号补充、产物详情与取消运行端点

提供获取 AI 反推业务摘要、保存用户补全信号、按 artifact_id 查询产物详情、
取消 Pipeline 运行，以及版本重跑指标记录。

router 定义保留在此文件中；路由处理函数与工具函数拆分至：
    - _pipeline_artifacts_helpers.py   常量与纯工具函数
    - _pipeline_artifacts_routes.py    查询类路由处理函数
    - _pipeline_artifacts_mutations.py 写入类路由处理函数

公开符号通过本文件 re-export，保持 import 路径不变。
"""
from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.api.v1.endpoints._pipeline_artifacts_helpers import (
    CANCELLABLE_STATUSES,
    PAYLOAD_TRUNCATE_THRESHOLD,
    _check_cancel_permission,
    _truncate_payload,
    record_version_rerun_metric,
)
from app.api.v1.endpoints._pipeline_artifacts_routes import (
    get_artifact_detail,
    get_inferred_summary,
    get_pipeline_summary,
)
from app.api.v1.endpoints._pipeline_artifacts_mutations import (
    cancel_pipeline_run,
    supplement_signals,
)

router = APIRouter(tags=["Pipeline管理"])

router.add_api_route(
    "/{run_id}/summary", get_pipeline_summary, methods=["GET"], response_model=ApiResponse
)
router.add_api_route(
    "/{run_id}/inferred-summary", get_inferred_summary, methods=["GET"], response_model=ApiResponse
)
router.add_api_route(
    "/{run_id}/artifacts/{artifact_id}", get_artifact_detail, methods=["GET"], response_model=ApiResponse
)
router.add_api_route(
    "/{run_id}/supplement-signals", supplement_signals, methods=["PUT"], response_model=ApiResponse
)
router.add_api_route(
    "/{run_id}/cancel", cancel_pipeline_run, methods=["POST"], response_model=ApiResponse
)

__all__ = [
    "router",
    "CANCELLABLE_STATUSES",
    "PAYLOAD_TRUNCATE_THRESHOLD",
    "_check_cancel_permission",
    "_truncate_payload",
    "record_version_rerun_metric",
    "get_artifact_detail",
    "get_inferred_summary",
    "get_pipeline_summary",
    "cancel_pipeline_run",
    "supplement_signals",
]
