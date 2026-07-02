from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
import logging
import re

from app.core.config import settings


# 仅匹配字符串开头的 MySQL 协议前缀，避免误匹配 URL 中间出现的 "mysql://" 子串。
# 形如：mysql://  mysql+aiomysql://  mysql+pymysql://  mysql+asyncmy://
_MYSQL_PROTOCOL_PATTERN = re.compile(r"^mysql(\+\w+)?://")


def _to_sync_url(url: str) -> str:
    """将 DATABASE_URL 转换为同步驱动版本，供 create_engine 使用。

    修复：docker-compose.yml 配置 mysql+aiomysql（异步驱动），但同步 SQLAlchemy
    create_engine 不支持异步驱动，会抛 NoSuchModuleError。此处统一替换为
    mysql+pymysql，确保同步引擎在 aiomysql 配置下也能工作。
    对已经是 pymysql 的 URL 是 no-op。
    """
    if not url:
        return url
    return _MYSQL_PROTOCOL_PATTERN.sub("mysql+pymysql://", url)


def _to_async_url(url: str) -> str:
    """将 DATABASE_URL 转换为异步驱动版本，供 create_async_engine 使用。

    与 _to_sync_url 互补：若配置为 mysql+pymysql，自动转为 mysql+aiomysql
    以便 AsyncEngine 使用异步驱动。对已经是 aiomysql 的 URL 是 no-op。
    """
    if not url:
        return url
    return _MYSQL_PROTOCOL_PATTERN.sub("mysql+aiomysql://", url)

Base = declarative_base()


def _apply_column_defaults(self, passed_keys):
    for table_column in self.__table__.columns:
        if table_column.default is not None:
            arg = getattr(table_column.default, 'arg', table_column.default)
            if callable(arg):
                continue
            attr_name = table_column.name
            if attr_name not in passed_keys:
                setattr(self, attr_name, arg)


_original_base_init = Base.__init__


def _base_init_with_defaults(self, **kwargs):
    column_names = {c.name for c in self.__table__.columns}
    column_kwargs = {k: v for k, v in kwargs.items() if k in column_names}
    extra_kwargs = {k: v for k, v in kwargs.items() if k not in column_names}

    _original_base_init(self, **column_kwargs)
    _apply_column_defaults(self, set(column_kwargs.keys()))

    for k, v in extra_kwargs.items():
        setattr(self, k, v)


Base.__init__ = _base_init_with_defaults

logger = logging.getLogger(__name__)


def create_database_engine(
    database_url: str,
    pool_size: int = 20,
    pool_timeout: int = 30,
    max_overflow: int = 10,
) -> Engine:
    # 同步引擎必须使用同步驱动；统一转换避免 aiomysql 配置下 NoSuchModuleError。
    return create_engine(
        _to_sync_url(database_url),
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=pool_timeout,
        echo=False,
    )


primary_engine = create_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

engine = primary_engine

secondary_url = settings.DATABASE_URL_SLAVE if settings.DATABASE_URL_SLAVE else settings.DATABASE_URL
secondary_engine = create_database_engine(
    secondary_url,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

PrimarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=primary_engine)
SecondarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=secondary_engine)

primary_scoped_session = scoped_session(PrimarySessionLocal)
secondary_scoped_session = scoped_session(SecondarySessionLocal)


# =============================================================
# 异步引擎层 - 渐进式 AsyncSession 迁移基础设施
# -------------------------------------------------------------
# 现有同步代码（PrimarySessionLocal + db.query）保持不变，继续工作。
# 新增代码可使用 AsyncPrimarySessionLocal + await db.execute(select(...))。
# 两套引擎共享同一数据库，连接池独立。
#
# 迁移路径：
#   1. service/endpoint 逐个改造为 async def + AsyncSession
#   2. db.query(Model).filter() → await db.execute(select(Model).where(...)).scalars().all()
#   3. db.add() 不变；db.commit() → await db.commit()
#   4. 全部迁移完成后删除同步引擎与 PrimarySessionLocal
# =============================================================


def create_async_database_engine(
    database_url: str,
    pool_size: int = 20,
    pool_timeout: int = 30,
    max_overflow: int = 10,
) -> AsyncEngine:
    """创建异步数据库引擎。

    使用 _to_async_url 确保驱动为 aiomysql（无论 .env 配置 pymysql 还是 aiomysql）。
    AsyncAdaptedQueuePool 是 SQLAlchemy 异步引擎的标准连接池。
    """
    return create_async_engine(
        _to_async_url(database_url),
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=pool_timeout,
        echo=False,
    )


async_primary_engine = create_async_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

async_secondary_engine = create_async_database_engine(
    secondary_url,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

AsyncPrimarySessionLocal = async_sessionmaker(
    bind=async_primary_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # AsyncSession 需在 commit 后避免同步 IO 触发 MissingGreenlet
)

AsyncSecondarySessionLocal = async_sessionmaker(
    bind=async_secondary_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)
