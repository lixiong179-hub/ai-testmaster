from app.api.v1.endpoints.pipeline_dashboard._overview import router as overview_router
from app.api.v1.endpoints.pipeline_dashboard._overview import get_dashboard_overview
from app.api.v1.endpoints.pipeline_dashboard._trends import (
    router as trends_router,
    get_token_usage,
    get_run_duration,
    get_step_latency,
    get_cache_hit_rate,
)

router = overview_router
for route in trends_router.routes:
    router.routes.append(route)

__all__ = [
    "router",
    "get_dashboard_overview",
    "get_token_usage",
    "get_run_duration",
    "get_step_latency",
    "get_cache_hit_rate",
]
