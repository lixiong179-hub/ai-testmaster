import asyncio
import sys
from collections.abc import AsyncGenerator

# Windows 平台必须使用 ProactorEventLoop 才能启动 Playwright 子进程
# （asyncio.create_subprocess_exec 在 SelectorEventLoop 下抛 NotImplementedError）。
# uvicorn 默认在 Windows 上设置 WindowsSelectorEventLoopPolicy，会导致
# BrowserControllerV2.initialize 调用 playwright.async_api 时崩溃。
# 此处提前覆盖策略，必须在 fastapi/uvicorn 任何其他导入之前执行。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exception import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
# R4-2：lifespan 的启动/关闭逻辑已拆分为可独立测试的单元
from app.core.lifecycle import shutdown as lifecycle_shutdown, startup as lifecycle_startup
from app.api.v1.endpoints import auth, project, file, test_task, report, test_point
from app.api.v1.endpoints import user, websocket, test_case, batch_locator, test_data
from app.api.v1.endpoints import execution_visualization, case_quality, execution, visibility
from app.api.v1.endpoints import requirement_link, ui_prototype, iteration, pipeline, review_inbox
from app.api.v1.endpoints import test_capability, audit_log, case_migration, case_refresh, ab_test
from app.api.v1.endpoints import generation_batch
from app.api.v1.endpoints import history_asset
from app.api.v1.endpoints import feature_flag
from app.api.v1.endpoints import ai_invocation
from app.api.v1.endpoints import prompt_template
from app.api.v1.endpoints import quality_rule
from app.api.v1.endpoints import bug as bug_endpoint
from app.api.v1.endpoints import ui_screens_batch
from app.api.v1.endpoints import quick_test
from app.api.v1.endpoints import agents, mcp_server, project_members, self_healing, impact_analysis, visual_ai
from app.api.v1.endpoints import oidc_endpoints, saml_endpoints, mfa_endpoints

setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """P3-6/R4-2: 应用生命周期管理。

    具体启动/关闭单元见 `app/core/lifecycle.py`，此处只负责顺序编排，
    使每个单元都能脱离 FastAPI 实例单独测试。
    """
    await lifecycle_startup()
    yield  # 应用运行中
    lifecycle_shutdown()


# OpenAPI 标签元数据（按功能域分组排序，用于 Swagger UI 文档组织）
TAGS_METADATA = [
    {"name": "认证管理", "description": "用户登录、登出与令牌管理"},
    {"name": "用户管理", "description": "用户信息查询、更新与密码修改"},
    {"name": "项目管理", "description": "测试项目的创建、查询与配置"},
    {"name": "文件管理", "description": "需求文件、截图等资源上传与管理"},
    {"name": "测试用例管理", "description": "用例CRUD、批量操作、工作流与版本管理"},
    {"name": "用例保鲜", "description": "过期用例扫描与保鲜建议审核"},
    {"name": "用例质量", "description": "用例质量评估与报告"},
    {"name": "质量规则", "description": "项目质量规则配置"},
    {"name": "跨设备用例迁移", "description": "跨设备用例迁移预览与提交"},
    {"name": "生成批次", "description": "AI用例生成批次管理与保存"},
    {"name": "测试点管理", "description": "测试点提取、导入与管理"},
    {"name": "测试数据", "description": "测试数据集管理"},
    {"name": "测试任务管理", "description": "测试任务创建、执行控制与查询"},
    {"name": "测试执行", "description": "测试执行可视化与配置"},
    {"name": "测试报告管理", "description": "测试报告生成与查询"},
    {"name": "测试能力管理", "description": "测试能力配置与查询"},
    {"name": "需求链接管理", "description": "需求与用例关联管理"},
    {"name": "批量定位器", "description": "UI元素批量定位"},
    {"name": "UI原型管理", "description": "UI原型项目与截图管理"},
    {"name": "UI截图批量", "description": "UI截图批量上传与处理"},
    {"name": "可见模式配置", "description": "用例业务/技术视图可见性配置"},
    {"name": "评审Inbox", "description": "用例评审收件箱管理"},
    {"name": "迭代管理", "description": "迭代版本管理"},
    {"name": "Pipeline管理", "description": "测试Pipeline创建与执行控制"},
    {"name": "Pipeline监控指标", "description": "Pipeline运行指标查询"},
    {"name": "Pipeline仪表盘", "description": "Pipeline仪表盘概览与趋势"},
    {"name": "AI调用审计", "description": "AI调用记录与成本统计"},
    {"name": "Prompt模板", "description": "AI提示词模板管理"},
    {"name": "特性开关", "description": "功能特性开关配置"},
    {"name": "A/B测试", "description": "A/B实验指标记录与汇总"},
    {"name": "历史资产", "description": "历史测试资产导入与分类"},
    {"name": "Bug缺陷管理", "description": "Bug缺陷列表查询"},
    {"name": "快速测试", "description": "一键网址驱动快速测试"},
    {"name": "审计日志", "description": "操作审计日志查询"},
]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """P2-8: 安全响应头中间件 — 统一注入安全相关的 HTTP 响应头。"""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI全自动测试平台后端API",
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan
)

# Prometheus 指标端点（可选监控，需 docker compose --profile monitoring 启用抓取）
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# 配置CORS中间件：统一由 settings 控制，移除 ["*"] 冗余回退。
# - DevSettings 继承基类 localhost 白名单（安全收紧，不再默认 "*"）
# - ProdSettings 默认 CORS_ORIGINS=""（强制显式配置，启动时由 ensure_secret_keys 校验）
# - CORS_ALLOW_HEADERS 默认为显式白名单（见 config.py）
# 空列表时 CORSMiddleware 将拒绝所有跨域请求，这是预期行为（强制显式配置）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_allow_methods_list,
    allow_headers=settings.cors_allow_headers_list,
)

# P2-8: 安全响应头中间件
app.add_middleware(SecurityHeadersMiddleware)

# 配置限流中间件（根据环境调整）
_rate_limit = 1000 if settings.ENVIRONMENT == "prod" else 5000  # 生产环境更严格
app.add_middleware(
    RateLimitMiddleware,
    max_requests=_rate_limit,  # 每分钟最多请求（根据环境动态配置）
    time_window=60  # 时间窗口为60秒
)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册API路由（所有模块均自带prefix，此处统一添加/api/v1前缀）
app.include_router(auth.router, prefix="/api/v1")
app.include_router(project.router, prefix="/api/v1")
app.include_router(quality_rule.router, prefix="/api/v1/projects")
app.include_router(test_point.router, prefix="/api/v1")
app.include_router(file.router, prefix="/api/v1")
app.include_router(test_task.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(test_case.router, prefix="/api/v1")
app.include_router(requirement_link.router, prefix="/api/v1")
app.include_router(batch_locator.router, prefix="/api/v1")
app.include_router(test_data.router, prefix="/api/v1")
app.include_router(execution_visualization.router, prefix="/api/v1")
app.include_router(case_quality.router, prefix="/api/v1")
app.include_router(execution.router, prefix="/api/v1")
app.include_router(visibility.router, prefix="/api/v1")
app.include_router(report.router, prefix="/api/v1")
app.include_router(ui_prototype.router, prefix="/api/v1")
app.include_router(ui_screens_batch.router, prefix="/api/v1")
app.include_router(iteration.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(review_inbox.router, prefix="/api/v1")
app.include_router(test_capability.router, prefix="/api/v1")
app.include_router(audit_log.router, prefix="/api/v1")
app.include_router(case_migration.router, prefix="/api/v1")
app.include_router(case_refresh.router, prefix="/api/v1/case-refresh")
app.include_router(ab_test.router, prefix="/api/v1/ab-test")
app.include_router(generation_batch.router, prefix="/api/v1/generation-batches")
app.include_router(history_asset.router, prefix="/api/v1/history-assets")
app.include_router(feature_flag.router, prefix="/api/v1/feature-flags")
app.include_router(ai_invocation.router, prefix="/api/v1/ai-invocation")
app.include_router(prompt_template.router, prefix="/api/v1/prompt-templates")
app.include_router(bug_endpoint.router, prefix="/api/v1/bugs")
app.include_router(quick_test.router, prefix="/api/v1/quick-test")
app.include_router(self_healing.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(mcp_server.router, prefix="/api/v1")
app.include_router(project_members.router, prefix="/api/v1")
app.include_router(impact_analysis.router, prefix="/api/v1")
app.include_router(visual_ai.router, prefix="/api/v1")
app.include_router(oidc_endpoints.router, prefix="/api/v1/auth")
app.include_router(saml_endpoints.router, prefix="/api/v1/auth")
app.include_router(mfa_endpoints.router, prefix="/api/v1/auth")


# 根路径
@app.get("/", summary="根路径", description="返回 API 名称与版本号，用于快速验证服务是否在线。")
def root() -> dict[str, str]:
    return {"message": "AI TestMaster API", "version": settings.APP_VERSION}


# 健康检查接口
@app.get("/health", summary="健康检查", description="检测 API 服务及依赖组件（数据库、Redis、AI 接口）的可用性状态。返回 status=healthy 或 degraded。")
def health_check() -> dict[str, object]:
    """健康检查接口（含依赖服务状态检测）"""
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {}
    }

    from app.db.database import check_db_connection
    db_ok = check_db_connection()
    health_status["services"]["database"] = "healthy" if db_ok else "unhealthy"
    if not db_ok:
        health_status["status"] = "degraded"

    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
        r.ping()
        r.close()
        health_status["services"]["redis"] = "healthy"
    except Exception:
        health_status["services"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"

    ai_configured = bool(settings.DEEPSEEK_API_KEY and not settings.DEEPSEEK_API_KEY.startswith("your"))
    health_status["services"]["ai_api"] = "configured" if ai_configured else "not_configured"

    return health_status


# 存活探针（Kubernetes livenessProbe）：仅表示进程可响应，不探测任何外部依赖
@app.get("/live", summary="存活探针", description="进程存活检查。仅返回进程可响应状态，不探测数据库、Redis 等外部依赖，避免依赖抖动导致容器被误重启。")
def live_check() -> dict[str, str]:
    """存活探针：永远返回 200，只要事件循环仍在调度。"""
    return {"status": "alive"}


# 就绪探针（Kubernetes readinessProbe）：关键依赖不可用时返回 503，从流量中摘除
@app.get("/ready", summary="就绪探针", description="就绪检查。探测数据库与 Redis 等关键依赖，全部可用返回 200，任一不可用返回 503。")
def ready_check() -> JSONResponse:
    """就绪探针：依赖不可用时返回 503，使实例从负载均衡中摘除。

    安全约束：失败时仅返回通用提示，不披露具体哪个依赖不可用，防止信息探测。
    """
    from app.db.database import check_db_connection
    db_ok = bool(check_db_connection())

    redis_ok = False
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
        r.ping()
        r.close()
        redis_ok = True
    except Exception:
        redis_ok = False

    if db_ok and redis_ok:
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "services": {"database": True, "redis": True},
            },
        )

    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "msg": "服务暂不可用，请稍后重试"},
    )
