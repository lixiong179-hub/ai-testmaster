"""
数据库操作辅助模块

提供数据库CRUD通用操作、事务管理、查询构建与分页查询的封装，
避免业务层重复编写样板代码，统一数据库操作范式。

核心类概览：
    - DatabaseHelper: 数据库CRUD通用操作，提供按ID查询、批量查询、
      全量查询、计数、创建、更新、删除、安全提交等方法
    - TransactionHelper: 事务处理辅助，提供两种事务模式——
      with_transaction（异常上抛模式）和 safe_execute（安全返回元组模式）
    - QueryHelper: 查询构建辅助，提供过滤条件构建和分页参数计算

便捷实例：
    - db_helper: DatabaseHelper 单例，直接调用静态方法
    - tx_helper: TransactionHelper 单例
    - query_helper: QueryHelper 单例

依赖关系：
    - SQLAlchemy: ORM核心，提供Session、查询构建器
    - loguru: 日志记录，用于异常场景的错误日志输出

使用示例：
    from app.core.db_helper import db_helper, tx_helper, query_helper, paginate_query
    user = db_helper.get_by_id(db, User, 1)
    items, total = paginate_query(db, db.query(User), page=2, page_size=20)
"""
from sqlalchemy.orm import Session
from typing import Optional, List, TypeVar, Type, Callable, Any
from sqlalchemy.exc import OperationalError, InterfaceError
from loguru import logger
import time

# 泛型类型变量，用于标注SQLAlchemy模型类的类型，
# 使方法返回值类型与传入的model参数类型一致，便于IDE类型推断
T = TypeVar('T')


class DatabaseHelper:
    """
    数据库CRUD通用操作辅助类

    职责：封装常用的数据库增删改查操作，提供统一的调用接口，
    减少业务层重复编写SQLAlchemy样板代码。

    设计意图：
        - 所有方法均为静态方法，无需实例化即可调用，降低使用成本
        - 方法内部自动处理commit/refresh，调用方无需手动提交
        - 删除和提交操作内置异常捕获与回滚，保证数据一致性

    关键属性：无（纯静态方法类）

    使用场景：
        - 简单的单表CRUD操作
        - 不需要复杂事务编排的场景
        - 需要快速获取/创建/更新单条记录的场景

    注意事项：
        - create/update/delete方法会自动commit，不适合在事务块内使用
          （事务块内应使用TransactionHelper）
        - update方法仅更新instance上已存在的属性，忽略不存在的字段
        - delete方法失败时返回False而非抛异常，调用方需检查返回值
    """

    @staticmethod
    def get_by_id(db: Session, model: Type[T], id: int) -> Optional[T]:
        """
        根据主键ID获取单条记录

        通过主键精确查找，返回单条记录或None。适用于需要按ID
        精确获取唯一记录的场景，如获取用户详情、获取测试用例等。

        Args:
            db: SQLAlchemy数据库会话，由FastAPI依赖注入提供
            model: SQLAlchemy模型类（如User、TestCase等），需包含id主键字段
            id: 要查询的记录主键值

        Returns:
            匹配的模型实例，未找到时返回None

        Raises:
            无显式异常，但数据库连接异常会向上传播

        注意：
            - 仅适用于以id为主键的模型，复合主键模型不适用
            - 查询结果不会自动刷新，如需最新数据请手动db.refresh()
        """
        return db.query(model).filter(model.id == id).first()

    @staticmethod
    def get_by_ids(db: Session, model: Type[T], ids: List[int]) -> List[T]:
        """
        根据ID列表批量获取记录（避免N+1查询）

        使用SQL IN子句一次性获取多条记录，避免在循环中逐条查询
        导致的N+1查询性能问题。适用于批量获取关联数据的场景，
        如根据用户ID列表批量获取用户信息。

        Args:
            db: SQLAlchemy数据库会话
            model: SQLAlchemy模型类，需包含id主键字段
            ids: 要查询的主键ID列表

        Returns:
            匹配的模型实例列表，无匹配时返回空列表

        Raises:
            无显式异常

        注意：
            - 空ids列表直接返回[]，避免生成无效的IN () SQL
            - 返回结果顺序不保证与ids参数顺序一致
            - 当ids数量极大时，需考虑数据库IN子句的长度限制
        """
        if not ids:
            return []
        return db.query(model).filter(model.id.in_(ids)).all()

    @staticmethod
    def get_all(db: Session, model: Type[T], skip: int = 0, limit: int = 100) -> List[T]:
        """
        获取所有记录（支持分页偏移）

        查询指定模型的全量记录，通过offset/limit实现分页。
        适用于后台管理列表、数据导出等需要遍历全量数据的场景。

        Args:
            db: SQLAlchemy数据库会话
            model: SQLAlchemy模型类
            skip: 跳过的记录数（偏移量），默认0表示从第一条开始
            limit: 返回的最大记录数，默认100条，防止一次加载过多数据

        Returns:
            模型实例列表

        Raises:
            无显式异常

        注意：
            - 默认limit=100，大数据量场景需显式指定更大的limit值
            - 大偏移量（skip值很大）时性能可能下降，建议使用游标分页替代
            - 返回结果无排序保证，如需排序请在调用前自行构建排序查询
        """
        return db.query(model).offset(skip).limit(limit).all()

    @staticmethod
    def count(db: Session, model: Type[T], **filters) -> int:
        """
        统计记录数量（支持过滤条件）

        对指定模型进行COUNT查询，可通过关键字参数传入过滤条件。
        适用于分页查询的总数计算、数据统计等场景。

        Args:
            db: SQLAlchemy数据库会话
            model: SQLAlchemy模型类
            **filters: 过滤条件，键为模型字段名，值为精确匹配值。
                       例如 count(db, User, role="admin", is_active=True)
                       将生成 WHERE role='admin' AND is_active=True

        Returns:
            符合条件的记录总数

        Raises:
            无显式异常

        注意：
            - 过滤条件仅支持精确匹配（filter_by），不支持范围/模糊查询
            - 复杂过滤条件请使用QueryHelper.build_filter_conditions构建
        """
        query = db.query(model)
        if filters:
            query = query.filter_by(**filters)
        return query.count()

    @staticmethod
    def create(db: Session, model: Type[T], **kwargs) -> T:
        """
        创建新记录

        根据关键字参数实例化模型并持久化到数据库，自动执行
        commit和refresh操作。适用于简单的单条记录创建场景。

        Args:
            db: SQLAlchemy数据库会话
            model: SQLAlchemy模型类
            **kwargs: 模型字段键值对，键为字段名，值为字段值。
                      例如 create(db, User, name="张三", email="zhangsan@test.com")

        Returns:
            创建成功后的模型实例（已refresh，包含数据库生成的字段如id、created_at）

        Raises:
            sqlalchemy.exc.IntegrityError: 违反唯一约束或外键约束时抛出
            sqlalchemy.exc.OperationalError: 数据库连接异常时抛出

        注意：
            - 此方法会自动commit，不适合在事务块内使用
            - 事务块内请使用 db.add(instance) + tx_helper.safe_commit()
            - kwargs中传入模型不存在的字段会触发SQLAlchemy异常
        """
        instance = model(**kwargs)
        db.add(instance)
        db.commit()
        # refresh使实例与数据库同步，获取自动生成的字段值（如自增id、默认值、onupdate字段）
        db.refresh(instance)
        return instance

    @staticmethod
    def update(db: Session, instance: T, **kwargs) -> T:
        """
        更新已有记录

        对已加载的模型实例进行字段更新，仅更新实例上已存在的属性，
        忽略不存在的字段名。自动执行commit和refresh。

        Args:
            db: SQLAlchemy数据库会话
            instance: 已加载的模型实例（通常由get_by_id等方法获取）
            **kwargs: 要更新的字段键值对，键为字段名，值为新值。
                      例如 update(db, user, name="李四", email="lisi@test.com")

        Returns:
            更新后的模型实例（已refresh，反映数据库最新状态）

        Raises:
            sqlalchemy.exc.IntegrityError: 更新后违反唯一约束时抛出
            sqlalchemy.exc.OperationalError: 数据库连接异常时抛出

        注意：
            - 此方法会自动commit，不适合在事务块内使用
            - hasattr检查确保只更新模型上已存在的属性，不存在的字段会被静默忽略
            - 传入None值会正常设置字段为None，不会跳过该字段
        """
        for key, value in kwargs.items():
            # 仅更新模型上已存在的属性，避免误设不存在的字段导致运行时异常
            if hasattr(instance, key):
                setattr(instance, key, value)
        db.commit()
        db.refresh(instance)
        return instance

    @staticmethod
    def delete(db: Session, instance: T) -> bool:
        """
        删除记录

        删除已加载的模型实例，内置异常捕获与回滚机制。
        与其他CRUD方法不同，此方法采用安全返回模式而非异常上抛。

        Args:
            db: SQLAlchemy数据库会话
            instance: 要删除的模型实例（通常由get_by_id等方法获取）

        Returns:
            True表示删除成功，False表示删除失败（已自动回滚）

        Raises:
            无显式异常，内部捕获所有异常并返回False

        注意：
            - 失败时自动回滚，不会影响其他操作
            - 调用方需检查返回值判断是否删除成功
            - 如果需要在删除失败时抛异常，请使用TransactionHelper.with_transaction
        """
        try:
            db.delete(instance)
            db.commit()
            return True
        except Exception as e:
            logger.error(
                f"删除记录失败: [{type(e).__name__}] {e}, "
                f"实例类型: {type(instance).__name__}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            db.rollback()
            return False

    @staticmethod
    def safe_commit(db: Session) -> bool:
        """
        安全提交事务

        封装commit操作，捕获提交过程中的异常并自动回滚。
        适用于手动管理事务的场景，如批量操作后统一提交。

        Args:
            db: SQLAlchemy数据库会话

        Returns:
            True表示提交成功，False表示提交失败（已自动回滚）

        Raises:
            无显式异常，内部捕获所有异常并返回False

        注意：
            - 适用于在事务块内手动add/modify后统一提交的场景
            - 失败时自动回滚，保证数据一致性
            - 如需在提交失败时获取异常详情，请使用TransactionHelper
        """
        try:
            db.commit()
            return True
        except Exception as e:
            logger.error(
                f"事务提交失败: [{type(e).__name__}] {e}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            db.rollback()
            return False


class TransactionHelper:
    """
    事务处理辅助类

    职责：封装数据库事务的提交与回滚逻辑，提供两种事务处理模式，
    适配不同的业务场景和错误处理策略。

    设计意图：
        - with_transaction: 异常上抛模式，适用于需要调用方自行处理异常的场景
        - safe_execute: 安全返回元组模式，适用于不需要异常上抛、只需判断成功与否的场景

    两种模式的核心区别：
        ┌──────────────────┬─────────────────────┬──────────────────────┐
        │     模式          │   失败时行为          │   返回值              │
        ├──────────────────┼─────────────────────┼──────────────────────┤
        │ with_transaction │  抛出原始异常(raise)  │   操作结果            │
        │ safe_execute     │  返回(False, 错误信息) │  (bool, result/str)  │
        └──────────────────┴─────────────────────┴──────────────────────┘

    使用场景：
        - with_transaction: 需要在外层try/except中统一处理异常，
          或需要根据异常类型做不同处理的场景
        - safe_execute: 只需判断操作是否成功，不需要区分异常类型的场景，
          如后台定时任务、批量操作等

    关键属性：无（纯静态方法类）
    """

    @staticmethod
    def with_transaction(
        db: Session, operation: Callable[..., Any], *args, **kwargs
    ) -> Any:
        """使用事务执行操作（异常上抛模式），对瞬时错误自动重试。"""
        last_exception = None
        for attempt in range(3):
            try:
                result = operation(*args, **kwargs)
                db.commit()
                return result
            except Exception as e:
                last_exception = e
                logger.error(
                    f"事务操作失败, 回滚(第{attempt + 1}次): "
                    f"[{type(e).__name__}] {e}, "
                    f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
                )
                try:
                    db.rollback()
                except Exception as rollback_err:
                    logger.error(f"回滚失败: {rollback_err}")
                if not isinstance(e, (OperationalError, InterfaceError)):
                    raise
                if attempt < 2:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise
        raise last_exception

    @staticmethod
    def safe_execute(
        db: Session, operation: Callable[..., Any], *args, **kwargs
    ) -> tuple[bool, Any]:
        """
        安全执行操作（安全返回元组模式）

        在事务中执行指定操作，成功则提交并返回(True, result)，
        失败则回滚并返回(False, 错误信息字符串)。不会抛出异常。

        适用场景：
            - 只需判断操作是否成功，不需要区分异常类型的场景
            - 后台定时任务、批量操作等不需要中断流程的场景
            - 需要记录失败原因但不需要异常处理的场景

        Args:
            db: SQLAlchemy数据库会话，用于事务的commit/rollback
            operation: 要执行的操作函数，该函数内执行数据库写操作
            *args: 传递给操作函数的位置参数
            **kwargs: 传递给操作函数的关键字参数

        Returns:
            元组 (success, result)：
                - success=True时，result为操作函数的返回值
                - success=False时，result为异常信息的字符串表示

        Raises:
            无显式异常，内部捕获所有异常

        使用示例：
            success, result = tx_helper.safe_execute(
                db, update_user, db, user_id, update_data
            )
            if not success:
                logger.warning(f"更新用户失败: {result}")
        """
        try:
            result = operation(*args, **kwargs)
            db.commit()
            return True, result
        except Exception as e:
            logger.error(
                f"操作失败: [{type(e).__name__}] {e}, "
                f"会话: active={db.is_active if hasattr(db, 'is_active') else 'N/A'}"
            )
            try:
                db.rollback()
            except Exception as rollback_err:
                logger.error(f"回滚失败: {rollback_err}")
            return False, str(e)


class QueryHelper:
    """
    查询构建辅助类

    职责：封装常用的查询条件构建逻辑，将过滤条件组装和分页参数计算
    从业务代码中抽离，提供声明式的查询构建接口。

    设计意图：
        - build_filter_conditions: 将字典形式的过滤条件转为SQLAlchemy表达式列表，
          支持与模型字段的动态匹配，避免手写大量filter链式调用
        - build_pagination: 将页码/每页数量转为offset/limit参数，
          统一分页参数的计算逻辑

    关键属性：无（纯静态方法类）

    使用场景：
        - 列表查询接口中动态构建过滤条件
        - 分页查询接口中计算偏移量
        - 与paginate_query函数配合使用完成完整的分页查询
    """

    @staticmethod
    def build_filter_conditions(model: Type[T], **filters) -> list:
        """
        构建过滤条件列表

        将关键字参数形式的过滤条件转换为SQLAlchemy的过滤表达式列表。
        仅处理模型上已存在的字段且值不为None的条件，自动忽略无效字段。

        过滤逻辑：
            1. 遍历filters中的每个键值对
            2. 检查值是否为None（None值表示"不筛选此字段"，跳过）
            3. 检查模型是否有该字段（防止传入无效字段名导致运行时异常）
            4. 生成 等值比较条件（model.field == value）并加入条件列表

        Args:
            model: SQLAlchemy模型类，用于获取字段属性
            **filters: 过滤条件键值对，键为模型字段名，值为精确匹配值。
                       None值会被自动跳过，不生成过滤条件。
                       例如 build_filter_conditions(User, role="admin", is_active=True, name=None)
                       将生成 [User.role=='admin', User.is_active==True]

        Returns:
            SQLAlchemy过滤表达式列表，可直接用query.filter(*conditions)应用。
            空列表表示无过滤条件。

        Raises:
            无显式异常

        注意：
            - 仅支持精确匹配（==），不支持范围查询、模糊查询、IN查询等
            - 复杂查询条件（如范围、模糊匹配）需在业务层自行构建
            - 多个条件之间为AND关系，需OR关系请使用sqlalchemy.or_手动构建
        """
        conditions = []
        for field, value in filters.items():
            # 跳过None值：None表示"不筛选此字段"，而非"筛选字段值为NULL的记录"
            # 同时检查模型是否有该字段，防止传入无效字段名
            if value is not None and hasattr(model, field):
                conditions.append(getattr(model, field) == value)
        return conditions

    @staticmethod
    def build_pagination(query, page: int = 1, page_size: int = 10):
        """
        构建分页查询参数

        将页码和每页数量转换为SQLAlchemy的offset和limit参数。
        分页计算公式：offset = (page - 1) * page_size

        计算逻辑说明：
            - page从1开始计数（对用户友好的页码表示）
            - offset从0开始计数（数据库偏移量）
            - 第1页: offset = (1-1) * 10 = 0，跳过0条，取前10条
            - 第2页: offset = (2-1) * 10 = 10，跳过前10条，取第11-20条
            - 第N页: offset = (N-1) * page_size

        Args:
            query: SQLAlchemy查询对象（此方法中未直接使用，保留用于扩展）
            page: 页码，从1开始计数，默认第1页
            page_size: 每页记录数，默认10条

        Returns:
            元组 (offset, limit)：
                - offset: 跳过的记录数，用于query.offset()
                - limit: 返回的最大记录数，用于query.limit()

        Raises:
            无显式异常

        注意：
            - page应 >= 1，传入0或负数会导致offset为负数，可能引发异常
            - page_size应 > 0，传入0会导致limit=0，返回空结果
            - 大偏移量时性能可能下降（深分页问题），建议使用游标分页替代
        """
        # 核心公式：页码从1开始，偏移量从0开始，因此需要减1
        offset = (page - 1) * page_size
        return offset, page_size


def paginate_query(db: Session, query, page: int = 1, page_size: int = 10):
    """
    分页查询通用函数

    对SQLAlchemy查询对象执行分页查询，同时返回当前页数据和总记录数。
    是最常用的分页查询入口，适用于绝大多数列表查询接口。

    执行流程：
        1. 先执行COUNT查询获取总记录数（用于计算总页数）
        2. 计算offset偏移量：offset = (page - 1) * page_size
        3. 执行带offset/limit的数据查询获取当前页记录
        4. 返回(当前页数据列表, 总记录数)元组

    Args:
        db: SQLAlchemy数据库会话（此参数保留用于扩展，当前未直接使用）
        query: SQLAlchemy查询对象，可包含filter、join等已构建的查询条件。
               注意：传入的query不应已包含offset/limit，否则会被覆盖。
        page: 页码，从1开始计数，默认第1页
        page_size: 每页记录数，默认10条

    Returns:
        元组 (items, total)：
            - items: 当前页的模型实例列表
            - total: 符合查询条件的总记录数（不受分页影响）

    Raises:
        无显式异常，数据库异常会向上传播

    注意：
        - 此函数会执行两次数据库查询：一次COUNT、一次SELECT
        - query参数应仅包含过滤条件，不应包含排序以外的offset/limit
        - 大数据量场景下COUNT查询可能较慢，可考虑缓存总数
        - 深分页（page值很大）时性能可能下降

    使用示例：
        query = db.query(User).filter(User.is_active == True)
        items, total = paginate_query(db, query, page=2, page_size=20)
        # items: 第21-40条用户记录
        # total: 活跃用户总数
    """
    # 先获取总记录数，用于前端计算总页数和页码范围
    total = query.count()
    # 计算偏移量：页码从1开始，偏移量从0开始
    offset = (page - 1) * page_size
    # 应用分页参数获取当前页数据
    items = query.offset(offset).limit(page_size).all()
    return items, total


# 导出便捷实例
# 虽然类方法均为静态方法，但提供实例便于统一导入和调用风格
# 使用方式：from app.core.db_helper import db_helper
db_helper = DatabaseHelper()
tx_helper = TransactionHelper()
query_helper = QueryHelper()
