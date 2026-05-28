from fastapi import APIRouter

from app.api.v1.endpoints.execution_core._execution import router as execution_router
from app.api.v1.endpoints.execution_core._analysis import router as analysis_router
from app.api.v1.endpoints.execution_core._analysis import (
    _perform_failure_analysis,
    _auto_create_bug_for_self_test,
    _generate_bug_no,
)
from app.api.v1.endpoints.execution_core._helpers import (
    verify_project_permission,
    get_task_or_404,
    SpeedReplayRequest,
)

router = APIRouter()

router.include_router(execution_router)
router.include_router(analysis_router)

__all__ = [
    "router",
    "_perform_failure_analysis",
    "_auto_create_bug_for_self_test",
    "_generate_bug_no",
]
