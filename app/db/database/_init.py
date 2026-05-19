from sqlalchemy import text
import logging

from app.db.database._engine import Base, primary_engine

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
