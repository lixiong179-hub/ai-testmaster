from app.db.database._engine import (
    Base,
    create_database_engine,
    primary_engine,
    engine,
    PrimarySessionLocal,
    primary_scoped_session,
    # Secondary 引擎懒加载工厂（未配置 slave 时退化为 primary）
    get_secondary_engine,
    get_secondary_session_local,
    get_secondary_scoped_session,
    # 异步引擎层（渐进式迁移用，详见 _engine.py 末尾说明）
    _to_sync_url,
    _to_async_url,
    create_async_database_engine,
    async_primary_engine,
    AsyncPrimarySessionLocal,
    get_async_secondary_engine,
    get_async_secondary_session_local,
)
from app.db.database._session import (
    get_db,
    get_read_db,
    get_db_context,
    get_read_db_context,
    async_get_db,
    async_get_read_db,
    async_get_db_context,
    async_get_read_db_context,
)
from app.db.database._init import (
    init_db,
    drop_db,
    check_db_connection,
    async_check_db_connection,
)


# 向后兼容：历史代码使用 secondary_engine / SecondarySessionLocal /
# secondary_scoped_session / async_secondary_engine / AsyncSecondarySessionLocal
# 直接导入。懒加载代理通过 _engine 模块的 __getattr__ 处理。
def __getattr__(name: str):
    if name == "secondary_engine":
        from app.db.database._engine import get_secondary_engine
        return get_secondary_engine() or primary_engine
    if name == "SecondarySessionLocal":
        from app.db.database._engine import get_secondary_session_local
        return get_secondary_session_local()
    if name == "secondary_scoped_session":
        from app.db.database._engine import get_secondary_scoped_session
        return get_secondary_scoped_session()
    if name == "async_secondary_engine":
        from app.db.database._engine import get_async_secondary_engine
        return get_async_secondary_engine() or async_primary_engine
    if name == "AsyncSecondarySessionLocal":
        from app.db.database._engine import get_async_secondary_session_local
        return get_async_secondary_session_local()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 同步层（现有代码继续使用）
    "Base",
    "create_database_engine",
    "primary_engine",
    "engine",
    "PrimarySessionLocal",
    "primary_scoped_session",
    "get_secondary_engine",
    "get_secondary_session_local",
    "get_secondary_scoped_session",
    # 向后兼容属性（通过 __getattr__ 代理）
    "secondary_engine",
    "SecondarySessionLocal",
    "secondary_scoped_session",
    "get_db",
    "get_read_db",
    "get_db_context",
    "get_read_db_context",
    "init_db",
    "drop_db",
    "check_db_connection",
    # 异步层（渐进式迁移新增代码使用）
    "create_async_database_engine",
    "async_primary_engine",
    "AsyncPrimarySessionLocal",
    "get_async_secondary_engine",
    "get_async_secondary_session_local",
    "async_secondary_engine",
    "AsyncSecondarySessionLocal",
    "async_get_db",
    "async_get_read_db",
    "async_get_db_context",
    "async_get_read_db_context",
    "async_check_db_connection",
]
