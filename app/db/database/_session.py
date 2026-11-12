from contextlib import contextmanager, asynccontextmanager
from collections.abc import AsyncGenerator, Generator
import logging

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database._engine import (
    PrimarySessionLocal,
    AsyncPrimarySessionLocal,
    get_secondary_session_local,
    get_async_secondary_session_local,
)

logger = logging.getLogger(__name__)


def get_db() -> Generator:
    db = PrimarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_read_db() -> Generator:
    """只读会话依赖，绑定到从库引擎。

    性能优化：未配置 DATABASE_URL_SLAVE 时退化为 PrimarySessionLocal，
    不再无谓创建独立连接池。
    """
    session_local = get_secondary_session_local()
    db = session_local()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    db = PrimarySessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"数据库操作错误: {e}")
        raise
    finally:
        db.close()


@contextmanager
def get_read_db_context() -> Generator[Session, None, None]:
    session_local = get_secondary_session_local()
    db = session_local()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库读取错误: {e}")
        raise
    finally:
        db.close()


# =============================================================
# 异步会话依赖 - 供 async def endpoint / service 使用
# -------------------------------------------------------------
# ⚠️ DEPRECATED（R2-1 / Q1，2026-11-10）：项目已决定收敛为
#    「全 sync + asyncio.to_thread」单范式。以下 4 个 async_* 入口
#    仅为过渡期兼容而保留，**禁止新增调用**；存量调用按 R2-1 阶段三
#    分批迁移为 await asyncio.to_thread(sync_fn, ...)。
#    阶段四完成前不物理删除（删除会立即打断 88 个仍 await 的端点）。
#    决策依据：docs/architecture/paradigm-convergence-decision.md
# -------------------------------------------------------------
# 用法（FastAPI 依赖注入）：
#   from app.db.database import async_get_db
#
#   @router.get("/items")
#   async def list_items(db: AsyncSession = Depends(async_get_db)):
#       result = await db.execute(select(Item).where(...))
#       return result.scalars().all()
#
# 用法（service 内上下文）：
#   async with async_get_db_context() as db:
#       db.add(obj)
#       await db.commit()
# =============================================================


async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    """异步数据库会话依赖，供 FastAPI async endpoint 注入使用。

    .. deprecated:: R2-1
        单范式收敛后应改用 ``Depends(get_db)`` + ``await asyncio.to_thread(...)``；
        本入口仅过渡期兼容，禁止新增调用。

    异常处理与同步 get_db 对齐：异常时回滚，最终关闭会话归还连接池。
    """
    async with AsyncPrimarySessionLocal() as db:
        try:
            yield db
        except Exception as e:
            logger.error(f"异步数据库会话错误: {e}")
            await db.rollback()
            raise


async def async_get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """异步只读会话依赖，绑定到从库引擎。

    性能优化：未配置 DATABASE_URL_SLAVE 时退化为 AsyncPrimarySessionLocal。
    """
    session_local = get_async_secondary_session_local()
    async with session_local() as db:
        try:
            yield db
        except Exception as e:
            logger.error(f"异步只读会话错误: {e}")
            await db.rollback()
            raise


@asynccontextmanager
async def async_get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """异步数据库上下文管理器，提交成功自动 commit，异常自动 rollback。

    与同步 get_db_context 行为对齐，用于 service 层 async 代码块。
    """
    async with AsyncPrimarySessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"异步数据库操作错误: {e}")
            raise


@asynccontextmanager
async def async_get_read_db_context() -> AsyncGenerator[AsyncSession, None]:
    """异步只读上下文管理器。"""
    session_local = get_async_secondary_session_local()
    async with session_local() as db:
        try:
            yield db
        except Exception as e:
            logger.error(f"异步只读操作错误: {e}")
            raise
