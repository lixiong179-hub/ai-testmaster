"""
迭代查询操作模块

提供迭代（Iteration）的所有只读查询操作，与 iteration_mutate.py 共同构成
迭代的完整CRUD能力。本模块仅包含查询函数，不涉及任何数据变更。

核心函数概览：
    - get_iteration: 根据ID获取迭代
    - get_iterations_by_project: 获取项目的迭代列表（按创建时间倒序+分页）
    - get_iterations_count_by_project: 获取项目的迭代数量

与Model/Schema的对应关系：
    - Model: app.models.iteration.Iteration

查询性能考虑：
    - 列表查询使用 order_by+offset+limit 实现分页，依赖 create_time 索引
    - count 查询仅返回整型，不加载完整对象，开销低
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.iteration import Iteration


def get_iteration(db: Session, iteration_id: int) -> Optional[Iteration]:
    """
    根据ID获取迭代

    Args:
        db: 数据库会话
        iteration_id: 迭代ID

    Returns:
        Optional[Iteration]: 迭代对象，不存在则返回None

    Note:
        此函数未做项目权限过滤，调用方需自行校验访问权限。
    """
    return db.query(Iteration).filter(Iteration.id == iteration_id).first()


def get_iterations_by_project(
    db: Session,
    project_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[Iteration]:
    """
    获取项目的迭代列表（按创建时间倒序+分页）

    按创建时间倒序排列，最新创建的迭代排在前面。

    Args:
        db: 数据库会话
        project_id: 项目ID
        skip: 跳过记录数，用于分页偏移
        limit: 返回记录上限

    Returns:
        List[Iteration]: 迭代列表，按创建时间倒序
    """
    return db.query(Iteration).filter(
        Iteration.project_id == project_id
    ).order_by(Iteration.create_time.desc()).offset(skip).limit(limit).all()


def get_iterations_count_by_project(db: Session, project_id: int) -> int:
    """
    获取项目的迭代数量

    用于分页计算总条数。

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        int: 迭代数量
    """
    return db.query(Iteration).filter(Iteration.project_id == project_id).count()
