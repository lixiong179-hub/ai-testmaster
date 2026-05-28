from fastapi import APIRouter

from app.api.v1.endpoints.pipeline_dashboard._overview import (
    router as overview_router,
    get_dashboard_overview,
)
from app.api.v1.endpoints.pipeline_dashboard._trends import (
    router as trends_router,
    get_token_usage,
    get_run_duration,
    get_step_latency,
    get_cache_hit_rate,
)

router = APIRouter(prefix="/dashboard", tags=["Pipeline仪表盘"])
router.include_router(overview_router)
router.include_router(trends_router)

__all__ = [
    "router",
    "get_dashboard_overview",
    "get_token_usage",
    "get_run_duration",
    "get_step_latency",
    "get_cache_hit_rate",
]
