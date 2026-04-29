"""
数据库连接配置模块 - 主从读写分离与连接池管理

本模块是整个应用的数据库基础设施层，负责：
1. 创建并管理主从数据库引擎（读写分离架构）
2. 提供多种数据库会话获取方式（FastAPI依赖注入 / 上下文管理器）
3. 数据库初始化与表结构智能同步
4. 数据库健康检查

核心类/函数概览：
- Base: SQLAlchemy ORM 声明式基类，所有模型类均需继承此类
- create_database_engine(): 工厂函数，创建带连接池的数据库引擎
- primary_engine / secondary_engine: 主库/从库引擎实例
- PrimarySessionLocal / SecondarySessionLocal: 会话工厂（非线程安全）
- primary_scoped_session / secondary_scoped_session: 线程安全会话（用于多线程场景）
- get_db() / get_read_db(): FastAPI 依赖项，分别获取主库/从库会话
- get_db_context() / get_read_db_context(): 上下文管理器，用于非请求场景获取会话
- init_db(): 数据库初始化入口（创建表 + 智能同步字段）
- drop_db(): 删除所有表（仅测试环境使用）
- check_db_connection(): 数据库连接健康检查

依赖关系：
- app.core.config.settings: 读取数据库连接URL、连接池参数等配置
- app.db.smart_sync: init_db() 中调用智能同步功能

架构设计说明：
    采用主从读写分离架构，primary_engine 负责所有写操作，secondary_engine 负责读操作。
    当未配置从库时（DATABASE_URL_SLAVE 为空），从库引擎自动降级为主库，
    保证单库部署场景下系统正常运行。
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from app.core.config import settings

# SQLAlchemy 声明式基类，所有 ORM 模型必须继承此类才能被 Base.metadata 管理
# 例如：class User(Base): __tablename__ = 'users'
Base = declarative_base()

# 模块级日志记录器，用于记录数据库连接、会话、同步等操作日志
logger = logging.getLogger(__name__)


def create_database_engine(database_url: str, pool_size: int = 20, pool_timeout: int = 30, max_overflow: int = 10):
    """
    创建带连接池的数据库引擎

    使用 SQLAlchemy 的 QueuePool 连接池实现，支持连接复用、自动回收和健康检测，
    适用于高并发 Web 服务场景。

    Args:
        database_url: 数据库连接URL，格式为 mysql+pymysql://user:pass@host:port/dbname
        pool_size: 连接池常驻连接数（默认20），即空闲时保持的连接数量。
            该值应根据数据库最大连接数和并发量综合设置，避免连接池耗尽。
        pool_timeout: 获取连接的超时时间（秒，默认30），超出此时间仍无法获取连接将抛异常。
            防止请求在连接池满时无限等待。
        max_overflow: 超出 pool_size 后允许临时创建的最大连接数（默认10）。
            即总连接数上限 = pool_size + max_overflow = 30。
            这些临时连接在归还后会被销毁，不会常驻连接池。

    Returns:
        sqlalchemy.engine.Engine: 配置好的数据库引擎实例

    Raises:
        sqlalchemy.exc.ArgumentError: 数据库URL格式错误时抛出
        sqlalchemy.exc.OperationalError: 无法连接数据库时抛出
    """
    return create_engine(
        database_url,
        poolclass=QueuePool,       # 使用队列式连接池，先进先出，保证连接均匀使用
        pool_size=pool_size,       # 连接池常驻连接数
        max_overflow=max_overflow, # 允许额外创建的临时连接数，防止高并发时请求阻塞
        pool_pre_ping=True,        # 每次从连接池取出连接时先发送 ping 包检测连接是否存活
                                    # 解决 MySQL 默认8小时断开空闲连接（wait_timeout）导致的
                                    # "MySQL server has gone away" 错误
        pool_recycle=3600,         # 连接最大存活时间（秒），3600 = 1小时
                                    # 早于 MySQL 默认的 wait_timeout(8小时) 回收，
                                    # 避免使用已被服务端关闭的连接
        pool_timeout=pool_timeout, # 获取连接的超时时间（秒）
        echo=False                 # 关闭SQL语句打印，生产环境应设为False避免日志泄露
    )


# ============================================================
# 主数据库引擎 - 负责所有写操作（INSERT/UPDATE/DELETE）
# ============================================================
primary_engine = create_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10)  # 使用 getattr 兼容旧配置，未配置时默认10
)

# 兼容性别名：部分模块（如 smart_sync）使用 engine 变量名引用主库引擎
# 保留此别名以避免大规模重构
engine = primary_engine

# ============================================================
# 从数据库引擎 - 负责读操作（SELECT），实现读写分离
# ============================================================
# 读写分离策略：写操作走主库，读操作走从库，降低主库压力
# 降级策略：若未配置从库URL，则从库引擎指向主库，保证单库部署可用
secondary_url = settings.DATABASE_URL_SLAVE if settings.DATABASE_URL_SLAVE else settings.DATABASE_URL
secondary_engine = create_database_engine(
    secondary_url,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10)
)

# ============================================================
# 会话工厂 - 用于创建数据库会话（Session）
# ============================================================
# sessionmaker 创建的是会话工厂类，调用()生成会话实例
# autocommit=False: 禁用自动提交，需显式调用 commit()，保证事务原子性
# autoflush=False: 禁用自动刷新，避免查询前自动 flush 导致意外SQL执行
PrimarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=primary_engine)
SecondarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=secondary_engine)

# ============================================================
# 线程安全会话 - scoped_session
# ============================================================
# scoped_session 基于线程本地存储（threading.local）实现，每个线程获取到的是同一个会话
# 适用于多线程环境（如后台任务、定时任务），确保同一线程内会话一致性
# 注意：FastAPI 的异步路由中不建议使用 scoped_session，应使用 get_db() 依赖项
primary_scoped_session = scoped_session(PrimarySessionLocal)
secondary_scoped_session = scoped_session(SecondarySessionLocal)


def get_db() -> Generator:
    """
    获取主数据库会话（用于写操作）- FastAPI 依赖注入方式

    本函数作为 FastAPI 的 Depends 依赖项使用，由框架管理会话的生命周期：
    - 请求开始时创建会话
    - 请求正常结束时关闭会话
    - 请求异常时回滚事务并关闭会话

    与 get_db_context() 的区别：
    - get_db(): 使用 yield 生成器，适合 FastAPI 依赖注入（Depends），不自动 commit
    - get_db_context(): 使用 @contextmanager，适合普通 Python 代码，自动 commit

    Usage:
        @router.get("/users")
        def list_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Yields:
        Session: 主数据库会话实例

    Raises:
        Exception: 数据库操作异常时回滚后重新抛出，由上层统一处理
    """
    db = PrimarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()  # 异常时回滚事务，保证数据一致性
        raise
    finally:
        db.close()  # 无论成功或异常，都必须关闭会话释放连接


def get_read_db() -> Generator:
    """
    获取从数据库会话（用于读操作）- FastAPI 依赖注入方式

    实现读写分离：所有只读查询通过此函数获取从库会话，减轻主库压力。
    当未配置从库时，从库引擎指向主库，降级为单库模式。

    Usage:
        @router.get("/projects")
        def list_projects(db: Session = Depends(get_read_db)):
            return db.query(Project).all()

    Yields:
        Session: 从数据库会话实例

    Raises:
        Exception: 数据库操作异常时回滚后重新抛出
    """
    db = SecondarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    上下文管理器方式获取主数据库会话（用于写操作）

    与 get_db() 的核心区别：
    1. get_db() 是 yield 生成器，用于 FastAPI Depends，不自动 commit
    2. get_db_context() 是 @contextmanager，用于非请求场景（如脚本、后台任务），自动 commit

    适用场景：
    - 后台定时任务
    - 命令行脚本
    - 非HTTP请求的业务逻辑
    - 单元测试中的数据库操作

    Usage:
        with get_db_context() as db:
            db.query(Model).all()
            # 退出 with 块时自动 commit，异常时自动 rollback
    """
    db = PrimarySessionLocal()
    try:
        yield db
        db.commit()  # 正常退出 with 块时自动提交事务
    except Exception as e:
        db.rollback()  # 异常时回滚，保证数据一致性
        logger.error(f"数据库操作错误: {e}")
        raise
    finally:
        db.close()


@contextmanager
def get_read_db_context():
    """
    上下文管理器方式获取从数据库会话（用于读操作）

    与 get_read_db() 的区别同 get_db_context() 与 get_db() 的区别：
    适用于非 FastAPI 请求场景的只读数据库操作。

    注意：读操作不需要 commit，因此此方法仅做异常处理和会话关闭，
    不调用 commit()（只读事务无需提交）。

    Usage:
        with get_read_db_context() as db:
            result = db.query(Model).all()
    """
    db = SecondarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库读取错误: {e}")
        raise
    finally:
        db.close()


def init_db():
    """
    初始化数据库 - 两步初始化策略

    本函数在应用启动时调用，采用两步策略确保数据库表结构完整：

    第一步：create_all - 创建缺失的表
        根据 Base.metadata 中注册的所有 ORM 模型，在数据库中创建尚不存在的表。
        注意：create_all 不会修改已存在表的结构（不会添加新字段），
        这是 SQLAlchemy 的设计限制。

    第二步：smart_sync - 智能同步已有表的字段
        检测 ORM 模型定义与实际数据库表结构的差异（新增字段），
        自动生成 ALTER TABLE 语句添加缺失的列。
        这解决了 create_all 无法处理字段变更的问题。

    与 Alembic 的关系：
        Alembic 是专业的数据库迁移工具，支持增删改列、索引等复杂变更。
        本函数的智能同步仅处理"新增字段"这一最常见场景，作为 Alembic 的补充。
        生产环境建议结合 Alembic 使用，但此函数可提供基础保障，
        防止因遗漏迁移脚本导致字段缺失的运行时错误。

    Raises:
        无显式抛出。smart_sync 失败不影响应用启动，仅记录警告日志。
    """
    logger.info("开始初始化数据库...")

    # 步骤1：创建缺失的表 - 根据 ORM 模型定义创建尚不存在的表
    # 此操作是幂等的：已存在的表不会被重复创建或修改
    Base.metadata.create_all(bind=primary_engine)
    logger.info("基础表结构检查完成")

    # 步骤2：智能同步已有表的字段 - 检测并添加 ORM 模型中新增但数据库中缺失的列
    # 这是 create_all 的补充，解决"新增字段后忘记执行迁移"的问题
    try:
        from app.db.smart_sync import smart_sync_database
        sync_report = smart_sync_database(Base, auto_fix=True)

        if sync_report.get('fixed', 0) > 0:
            # 有字段被自动修复，记录警告级别日志以便运维关注
            logger.warning(f"数据库自动修复: {sync_report['summary']}")
        else:
            logger.info("数据库表结构已完全同步")

    except Exception as e:
        # 智能同步失败不阻塞应用启动，仅记录警告
        # 可能的失败原因：数据库权限不足、表结构冲突等
        logger.warning(f"数据库智能同步跳过（非致命）: {e}")

    logger.info("数据库初始化完成")


def drop_db():
    """
    删除所有数据库表 - 仅用于测试环境

    危险操作！此函数会删除 Base.metadata 中注册的所有表及其数据。
    生产环境严禁调用。

    典型使用场景：
    - 单元测试的 setUp/tearDown 中重建干净的数据库状态
    - 开发环境重置数据库
    """
    logger.warning("开始删除所有数据库表...")
    Base.metadata.drop_all(bind=primary_engine)
    logger.warning("所有数据库表已删除")


def check_db_connection() -> bool:
    """
    检查数据库连接是否正常 - 健康检查

    通过执行 SELECT 1 语句验证数据库连接是否可用。
    常用于：
    - 应用启动时的健康检查
    - Kubernetes liveness/readiness 探针
    - 监控系统的数据库可用性检测

    Returns:
        bool: True 表示连接正常，False 表示连接异常
    """
    try:
        with primary_engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # 最轻量的SQL，仅验证连接可用性
        return True
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}")
        return False
