from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
import logging

from app.db.database._engine import Base, primary_engine, async_primary_engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    logger.info("开始初始化数据库...")

    Base.metadata.create_all(bind=primary_engine)
    logger.info("基础表结构检查完成")

    try:
        from app.db.smart_sync import smart_sync_database
        sync_report = smart_sync_database(Base, auto_fix=True)

        if sync_report.get('fixed', 0) > 0:
            logger.warning(f"数据库自动修复: {sync_report['summary']}")
        else:
            logger.info("数据库表结构已完全同步")

    except Exception as e:
        logger.warning(f"数据库智能同步跳过（非致命）: {e}")

    logger.info("数据库初始化完成")


def drop_db() -> None:
    logger.warning("开始删除所有数据库表...")
    Base.metadata.drop_all(bind=primary_engine)
    logger.warning("所有数据库表已删除")


def check_db_connection() -> bool:
    try:
        with primary_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}")
        return False


async def async_check_db_connection(
    engine: AsyncEngine | None = None,
) -> bool:
    """异步数据库连接检查，供 async lifespan / 健康检查接口使用。

    Args:
        engine: 可选的异步引擎实例，未指定时使用全局 async_primary_engine。

    Returns:
        bool: 连接正常返回 True，否则 False。
    """
    target_engine = engine or async_primary_engine
    try:
        async with target_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"异步数据库连接检查失败: {e}")
        return False
