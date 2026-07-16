from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.decl_api import _declarative_constructor
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


class ModelBase:
    """所有 ORM 模型的显式基类。

    通过 declarative_base(cls=ModelBase, constructor=ModelBase.__init__) 注入：
    ModelBase 出现在 Base 的 MRO 中，便于 IDE 跳转与类型检查；同时
    constructor= 显式覆盖 SQLAlchemy 默认的 _declarative_constructor，
    避免回到模块级 Base.__init__ = ... 猴子补丁。

    提供两项构造期行为（与历史猴子补丁完全等价）：
    1. 非 callable 列默认值在实例化时即填充（不等待 flush），
       便于业务代码在 add 之前读取 model.is_deleted / model.review_status 等。
    2. 未在 __table__.columns 中的 kwargs 通过 setattr 设置到实例，
       兼容历史调用约定。

    callable 默认值（如 default=utcnow）仍由 SQLAlchemy 在 flush 时触发，
    本类不干预。
    """

    def __init__(self, **kwargs: Any) -> None:
        column_names = {c.name for c in self.__table__.columns}
        column_kwargs = {k: v for k, v in kwargs.items() if k in column_names}
        extra_kwargs = {k: v for k, v in kwargs.items() if k not in column_names}

        _declarative_constructor(self, **column_kwargs)
        self._apply_column_defaults(set(column_kwargs.keys()))

        for k, v in extra_kwargs.items():
            setattr(self, k, v)

    def _apply_column_defaults(self, passed_keys: set[str]) -> None:
        for table_column in self.__table__.columns:
            if table_column.default is None:
                continue
            arg = getattr(table_column.default, "arg", table_column.default)
            if callable(arg):
                continue
            if table_column.name not in passed_keys:
                setattr(self, table_column.name, arg)


Base = declarative_base(cls=ModelBase, constructor=ModelBase.__init__)
# P3-2: 标记为非测试类，避免 pytest 把 Base（及别名 TestCaseBase）误识别为测试类
# 触发 PytestCollectionWarning: cannot collect test class 'Base'
Base.__test__ = False

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


# 性能优化：同步引擎实际负载低（仅遗留端点与 CLI 使用），使用 DB_SYNC_POOL_SIZE
# 避免 sync+async 双引擎连接池翻倍（原 60 连接→现 10 连接 + async 30 = 40 上限）。
primary_engine = create_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_SYNC_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=settings.DB_SYNC_MAX_OVERFLOW,
)

engine = primary_engine

PrimarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=primary_engine)

primary_scoped_session = scoped_session(PrimarySessionLocal)


# =============================================================
# Secondary 引擎层 - 懒加载
# -------------------------------------------------------------
# 性能优化：业务代码零引用 secondary_engine（grep 验证），且未配置
# DATABASE_URL_SLAVE 时 secondary 与 primary 指向同一数据库，重复创建
# 连接池纯属浪费。改为懒加载工厂函数，仅在显式启用 slave 时才创建。
# 历史导出的 secondary_engine / SecondarySessionLocal / secondary_scoped_session
# 模块属性保留为 property-like 兼容入口，但实际使用应通过 get_secondary_*。
# =============================================================

_secondary_engine_cache: Optional[Engine] = None
_secondary_session_local_cache: Optional[sessionmaker] = None
_secondary_scoped_session_cache: Optional[scoped_session] = None


def _has_slave_url() -> bool:
    """判断是否实际配置了 DATABASE_URL_SLAVE。"""
    return bool(settings.DATABASE_URL_SLAVE)


def get_secondary_engine() -> Optional[Engine]:
    """懒加载 secondary 同步引擎，未配置 slave 时返回 None。"""
    global _secondary_engine_cache
    if not _has_slave_url():
        return None
    if _secondary_engine_cache is None:
        _secondary_engine_cache = create_database_engine(
            settings.DATABASE_URL_SLAVE,  # type: ignore[arg-type]
            pool_size=settings.DB_SYNC_POOL_SIZE,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            max_overflow=settings.DB_SYNC_MAX_OVERFLOW,
        )
    return _secondary_engine_cache


def get_secondary_session_local() -> sessionmaker:
    """获取 secondary SessionLocal，未配置 slave 时退化为 PrimarySessionLocal。"""
    global _secondary_session_local_cache
    if not _has_slave_url():
        return PrimarySessionLocal
    if _secondary_session_local_cache is None:
        engine_ = get_secondary_engine()
        _secondary_session_local_cache = sessionmaker(
            autocommit=False, autoflush=False, bind=engine_
        )
    return _secondary_session_local_cache  # type: ignore[return-value]


def get_secondary_scoped_session() -> scoped_session:
    """获取 secondary scoped_session，未配置 slave 时退化为 primary_scoped_session。"""
    global _secondary_scoped_session_cache
    if not _has_slave_url():
        return primary_scoped_session
    if _secondary_scoped_session_cache is None:
        session_local = get_secondary_session_local()
        _secondary_scoped_session_cache = scoped_session(session_local)
    return _secondary_scoped_session_cache  # type: ignore[return-value]


# 向后兼容：保留模块属性访问路径（懒加载代理）
# 注意：访问 secondary_engine / SecondarySessionLocal / secondary_scoped_session
# 在未配置 slave 时会得到 primary 的等价物，行为与历史一致但不再创建额外连接池。
def __getattr__(name: str) -> Any:
    if name == "secondary_engine":
        return get_secondary_engine() or primary_engine
    if name == "SecondarySessionLocal":
        return get_secondary_session_local()
    if name == "secondary_scoped_session":
        return get_secondary_scoped_session()
    if name == "async_secondary_engine":
        return get_async_secondary_engine() or async_primary_engine
    if name == "AsyncSecondarySessionLocal":
        return get_async_secondary_session_local()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


# 异步引擎为 ASGI 主路径，使用 DB_ASYNC_POOL_SIZE（默认 20，与原值一致）
async_primary_engine = create_async_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_ASYNC_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=settings.DB_ASYNC_MAX_OVERFLOW,
)

AsyncPrimarySessionLocal = async_sessionmaker(
    bind=async_primary_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # AsyncSession 需在 commit 后避免同步 IO 触发 MissingGreenlet
)


# Secondary 异步引擎懒加载（同同步引擎策略）
_async_secondary_engine_cache: Optional[AsyncEngine] = None
_async_secondary_session_local_cache: Optional[async_sessionmaker] = None


def get_async_secondary_engine() -> Optional[AsyncEngine]:
    """懒加载 secondary 异步引擎，未配置 slave 时返回 None。"""
    global _async_secondary_engine_cache
    if not _has_slave_url():
        return None
    if _async_secondary_engine_cache is None:
        _async_secondary_engine_cache = create_async_database_engine(
            settings.DATABASE_URL_SLAVE,  # type: ignore[arg-type]
            pool_size=settings.DB_ASYNC_POOL_SIZE,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            max_overflow=settings.DB_ASYNC_MAX_OVERFLOW,
        )
    return _async_secondary_engine_cache


def get_async_secondary_session_local() -> async_sessionmaker:
    """获取 secondary AsyncSessionLocal，未配置 slave 时退化为 AsyncPrimarySessionLocal。"""
    global _async_secondary_session_local_cache
    if not _has_slave_url():
        return AsyncPrimarySessionLocal
    if _async_secondary_session_local_cache is None:
        engine_ = get_async_secondary_engine()
        _async_secondary_session_local_cache = async_sessionmaker(
            bind=engine_,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _async_secondary_session_local_cache  # type: ignore[return-value]
