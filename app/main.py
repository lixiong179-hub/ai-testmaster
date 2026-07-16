import asyncio
import os
import secrets
import sys
from typing import AsyncGenerator

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
from starlette.responses import Response
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.config import settings, init_directories
from app.core.logging import setup_logging
from app.core.exception import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
from app.db.database import init_db
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash
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
from loguru import logger

setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """P3-6: 应用生命周期管理（替代已弃用的 on_event startup）"""
    # 启动阶段
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 正在启动...")

    # 初始化目录结构
    init_directories()

    # 初始化数据库
    init_db()

    # 确保存在默认管理员
    db = None
    try:
        db = PrimarySessionLocal()
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin_password = settings.ADMIN_INITIAL_PASSWORD or os.getenv("ADMIN_INITIAL_PASSWORD")
            if not admin_password:
                admin_password = secrets.token_urlsafe(16)
                logger.warning(
                    "未设置 ADMIN_INITIAL_PASSWORD，已生成随机管理员密码。"
                    "请通过环境变量 ADMIN_INITIAL_PASSWORD 配置！"
                )
            admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash(admin_password),
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.commit()
    except Exception as e:
        logger.warning(f"初始化默认管理员失败（非致命）: {e}")
        if db:
            db.rollback()
    finally:
        if db:
            db.close()

    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动成功 (环境: {settings.ENVIRONMENT})")

    # 启动 APScheduler 定时任务调度器
    from app.services.scheduler_service import start_scheduler
    start_scheduler()

    yield  # 应用运行中

    # 关闭阶段（清理资源）
    # 关闭 APScheduler 调度器
    from app.services.scheduler_service import shutdown_scheduler
    shutdown_scheduler()

    logger.info("应用正在关闭...")


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
