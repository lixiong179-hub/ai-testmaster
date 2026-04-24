import os
import secrets
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, init_directories
from app.core.logging import setup_logging
from app.core.exception import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
from app.db.database import init_db
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash
from app.api.v1.endpoints import auth, project, file, test_task, report, test_point, user, websocket, test_case, batch_locator, test_data, execution_visualization, case_quality, execution, visibility, requirement_link, ui_prototype, iteration
from loguru import logger

setup_logging(log_level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
            admin_password = os.getenv("ADMIN_INITIAL_PASSWORD")
            if not admin_password:
                if settings.ENVIRONMENT == "prod":
                    admin_password = secrets.token_urlsafe(16)
                    logger.warning(
                        "生产环境未设置 ADMIN_INITIAL_PASSWORD，"
                        "已生成随机管理员密码。请通过环境变量配置！"
                    )
                else:
                    admin_password = "admin123"
                    logger.warning(
                        "开发环境使用默认管理员密码(admin123)，"
                        "生产环境请务必设置 ADMIN_INITIAL_PASSWORD 环境变量"
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

    yield  # 应用运行中

    # 关闭阶段（清理资源）
    logger.info("应用正在关闭...")


# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI全自动测试平台后端API",
    lifespan=lifespan
)

# 配置CORS中间件（根据环境动态配置）
# 生产环境禁止使用通配符，开发环境允许
cors_origins = settings.cors_origins_list if settings.cors_origins_list else (["*"] if settings.ENVIRONMENT == "dev" else [])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_allow_methods_list if settings.cors_allow_methods_list else ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=settings.cors_allow_headers_list if settings.cors_allow_headers_list else ["*"],
)

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
app.include_router(iteration.router, prefix="/api/v1")


# 根路径
@app.get("/")
def root():
    return {"message": "AI TestMaster API", "version": settings.APP_VERSION}


# 健康检查接口
@app.get("/health")
def health_check():
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
