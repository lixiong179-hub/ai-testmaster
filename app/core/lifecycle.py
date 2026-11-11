"""应用生命周期单元（R4-2：lifespan 拆分）。

原 `app/main.py::lifespan` 将「初始化目录 → 初始化数据库 → 默认管理员 →
启动调度器 → 关闭调度器」全部内联在一个函数中，无法单独测试。此处拆为
5 个可独立调用的单元 + 1 组顺序编排函数。

单元清单（与 main.py 原行号一一对应）：
    1. ``startup_init_directories``   —— 初始化目录结构
    2. ``startup_init_db``            —— 初始化数据库
    3. ``startup_ensure_default_admin`` —— 确保存在默认管理员（非致命容错）
    4. ``startup_scheduler``          —— 启动 APScheduler 定时任务
    5. ``shutdown_scheduler``         —— 优雅关闭 APScheduler

设计约束：
    - 所有单元均**不接收 FastAPI 实例**，可直接在测试中调用；
    - 单元 3 保留原有「异常仅告警、回滚、不向上抛出」的非致命语义；
    - 调度器相关导入保持函数内延迟导入，避免模块导入期拉起 APScheduler。
"""
from __future__ import annotations

import os
import secrets

from loguru import logger

from app.core.config import init_directories, settings
from app.db.database import PrimarySessionLocal, init_db
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


def startup_init_directories() -> None:
    """初始化运行所需目录结构（上传目录、日志目录等）。"""
    init_directories()


def startup_init_db() -> None:
    """初始化数据库（建表 / 索引 / 会话配置）。"""
    init_db()


def startup_ensure_default_admin() -> None:
    """确保存在默认管理员账号。

    默认密码优先取 ``settings.ADMIN_INITIAL_PASSWORD``，其次取同名环境变量；
    两者都没有时生成一次随机密码并告警（不落库明文）。

    非致命语义（务必保持）：任何异常仅记录告警并回滚，**不向上抛出**，
    否则数据库短暂不可用会导致整个应用无法启动。
    """
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


def startup_scheduler() -> None:
    """启动 APScheduler 定时任务调度器（延迟导入，避免导入期副作用）。"""
    from app.services.scheduler_service import start_scheduler

    start_scheduler()


def shutdown_scheduler() -> None:
    """优雅关闭 APScheduler 定时任务调度器。"""
    from app.services.scheduler_service import shutdown_scheduler as _shutdown_scheduler

    _shutdown_scheduler()


async def startup() -> None:
    """启动阶段编排：按固定顺序执行 4 个启动单元。"""
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 正在启动...")
    startup_init_directories()
    startup_init_db()
    startup_ensure_default_admin()
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动成功 (环境: {settings.ENVIRONMENT})")
    startup_scheduler()


def shutdown() -> None:
    """关闭阶段编排：关闭调度器并记录日志。"""
    shutdown_scheduler()
    logger.info("应用正在关闭...")
