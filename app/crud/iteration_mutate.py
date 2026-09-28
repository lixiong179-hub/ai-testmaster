"""
迭代变更操作模块

提供迭代（Iteration）的所有变更操作（创建/更新/删除），
与 iteration_query.py 共同构成迭代的完整CRUD能力。
本模块仅包含变更函数，不涉及对外暴露的查询操作。

核心函数概览：
    - create_iteration: 创建迭代（同名校验，防止项目下重复）
    - update_iteration: 更新迭代（重命名时校验同名，自动更新update_time）
    - delete_iteration: 删除迭代（支持清理回调，异常时自动回滚）

与Model/Schema的对应关系：
    - Model: app.models.iteration.Iteration

事务处理方式：
    - create_iteration: 仅 flush 不 commit，由调用方控制事务边界
    - update_iteration: 自动 commit 并 refresh
    - delete_iteration: 自动 commit，异常时 rollback

软删除/硬删除：
    - delete_iteration 为硬删除，物理移除数据库记录
    - 通过 cleanup_callback 参数支持删除前的关联资源清理

跨类操作说明：
    - create/update/delete 内部包含存在性与同名校验的 SELECT 查询，
      这些查询与具体变更逻辑强耦合（如重命名校验需排除自身），
      非通用查询，故按"保守处理"原则保留在本模块内。
"""
from typing import Optional, Callable
from sqlalchemy.orm import Session
from app.models.iteration import Iteration
from datetime import datetime
from app.utils.db_time import utcnow

MAX_ITERATION_NAME_LENGTH = 200


def _normalize_iteration_name(name: str) -> str:
    return name[:MAX_ITERATION_NAME_LENGTH]


def create_iteration(
    db: Session,
    project_id: int,
    name: str,
    version: str = "v1.0",
    description: Optional[str] = None,
    status: str = "draft",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Iteration:
    """
    创建迭代

    创建一个新的迭代记录，默认状态为draft。创建前校验项目下是否存在同名迭代，
    防止重复。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        name: 迭代名称，同一项目下必须唯一
        version: 版本号，默认"v1.0"
        description: 迭代描述（可选）
        status: 迭代状态，默认"draft"，可选in_pipeline/in_review/finalized/archived
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        Iteration: 创建成功后的迭代对象（已flush，由调用方控制commit）

    Raises:
        ValueError: 项目下已存在同名迭代时抛出

    Note:
        同名校验范围限定在项目内（project_id + name联合唯一），
        不同项目下允许存在同名迭代。
    """
    # 同名校验：防止项目下出现重复迭代名称
    name = _normalize_iteration_name(name)

    existing = db.query(Iteration).filter(
        Iteration.project_id == project_id,
        Iteration.name == name
    ).first()
    if existing:
        raise ValueError(f"项目下已存在同名迭代: {name}")

    db_iteration = Iteration(
        project_id=project_id,
        name=name,
        version=version,
        description=description,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    db.add(db_iteration)
    db.flush()
    return db_iteration


def update_iteration(db: Session, iteration_id: int, **kwargs) -> Optional[Iteration]:
    """
    更新迭代

    通过kwargs动态更新迭代字段。若更新name字段，会先校验项目下是否存在同名迭代
    （排除自身），防止重命名冲突。自动更新update_time。

    Args:
        db: 数据库会话
        iteration_id: 迭代ID
        **kwargs: 需要更新的字段键值对，如name/version/status/description等

    Returns:
        Optional[Iteration]: 更新后的迭代对象，不存在则返回None

    Raises:
        ValueError: 重命名时项目下已存在同名迭代（排除自身后）

    Note:
        - 仅更新值为非None的字段，None值字段会被跳过
        - 自动更新update_time为UTC当前时间
        - 重命名校验时排除自身（Iteration.id != iteration_id），
          允许保持原名称不变
    """
    db_iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if not db_iteration:
        return None

    # 禁止直接修改 status，必须通过 iteration_service.transition_iteration_status
    if "status" in kwargs:
        raise ValueError(
            "禁止直接修改 iteration.status，请使用 iteration_service.transition_iteration_status()"
        )

    # 重命名校验：若更新name字段，检查项目下是否存在同名迭代（排除自身）
    if "name" in kwargs and kwargs["name"] is not None:
        kwargs["name"] = _normalize_iteration_name(kwargs["name"])
        existing = db.query(Iteration).filter(
            Iteration.project_id == db_iteration.project_id,
            Iteration.name == kwargs["name"],
            Iteration.id != iteration_id  # 排除自身，允许保持原名称
        ).first()
        if existing:
            raise ValueError(f"项目下已存在同名迭代: {kwargs['name']}")

    # 仅更新值为非None的字段
    for key, value in kwargs.items():
        if value is not None:
            setattr(db_iteration, key, value)

    # 自动更新修改时间为UTC当前时间
    db_iteration.update_time = utcnow()
    db.commit()
    db.refresh(db_iteration)
    return db_iteration


def delete_iteration(db: Session, iteration_id: int, cleanup_callback: Optional[Callable[[], None]] = None) -> bool:
    """
    删除迭代

    硬删除迭代记录，支持通过cleanup_callback在删除前清理关联资源。
    异常时自动回滚事务，确保数据一致性。

    Args:
        db: 数据库会话
        iteration_id: 迭代ID
        cleanup_callback: 可选的清理回调函数，在迭代删除前调用（如清理关联资源）。
            回调函数无参数，由调用方通过闭包传入所需的上下文。

    Returns:
        bool: 删除成功返回True，迭代不存在返回False

    Raises:
        Exception: cleanup_callback或删除操作异常时重新抛出，事务已回滚

    Note:
        典型使用场景：
        1. 删除迭代前，将关联文件的iteration_id设为None（解绑）
        2. 删除迭代前，将关联UI原型项目的iteration_id设为None
        3. 回调函数通过闭包捕获db和iteration_id，执行清理逻辑

    Warning:
        cleanup_callback中的操作与迭代删除在同一事务中，
        若回调抛出异常，整个事务会回滚（包括迭代删除本身）。
    """
    db_iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if not db_iteration:
        return False

    try:
        # 先执行清理回调，再删除迭代，确保关联资源在迭代存在时被正确处理
        if cleanup_callback:
            cleanup_callback()

        db.delete(db_iteration)  # 硬删除：物理移除数据库记录
        db.commit()
        return True
    except Exception:
        db.rollback()  # 异常时回滚事务，确保数据一致性
        raise
