"""
测试任务查询操作模块

提供测试任务（TestTask）的所有只读查询操作，与 test_task_mutate.py 共同构成
测试任务的完整CRUD能力。本模块仅包含查询函数，不涉及任何数据变更。

核心函数概览：
    - get_test_task_by_id: 根据ID获取测试任务（带项目隔离）
    - get_test_tasks_by_project: 获取项目的测试任务列表（支持状态过滤+分页+时间倒序）
    - get_test_tasks_count: 获取测试任务数量（用于分页计算）

与Model/Schema的对应关系：
    - Model: app.models.test_task.TestTask

查询性能考虑：
    - status 使用 `is not None` 判断而非布尔判断，因为0也是有效值（等待执行）
    - 列表查询使用 order_by+offset+limit 实现分页，依赖 create_time 索引
    - count 查询仅返回整型，不加载完整对象，开销低
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.test_task import TestTask


def get_test_task_by_id(db: Session, task_id: int, project_id: int) -> Optional[TestTask]:
    """
    根据ID获取测试任务

    通过任务ID和项目ID联合过滤，确保在项目维度下定位唯一任务。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[TestTask]: 测试任务对象，不存在则返回None
    """
    return db.query(TestTask).filter(
        TestTask.id == task_id,
        TestTask.project_id == project_id
    ).first()


def get_test_tasks_by_project(
    db: Session,
    project_id: int,
    status: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestTask]:
    """
    获取项目的测试任务列表（支持状态过滤+分页+时间倒序）

    按创建时间倒序排列，最新的任务排在前面。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 任务状态（可选），0=等待/1=执行中/2=完成/3=失败/4=停止
        skip: 偏移量，用于分页
        limit: 限制数

    Returns:
        List[TestTask]: 测试任务列表，按创建时间倒序

    Note:
        status 使用 `is not None` 判断，因为0也是有效值（等待执行）。
    """
    query = db.query(TestTask).filter(TestTask.project_id == project_id)

    # status=0 是有效值，必须用 is not None 判断
    if status is not None:
        query = query.filter(TestTask.status == status)

    # 按创建时间倒序，最新任务排在前面
    return query.order_by(TestTask.create_time.desc()).offset(skip).limit(limit).all()


def get_test_tasks_count(db: Session, project_id: int, status: Optional[int] = None) -> int:
    """
    获取项目的测试任务数量

    用于分页计算总条数，查询条件与 get_test_tasks_by_project 一致。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 任务状态（可选）

    Returns:
        int: 符合条件的任务数量
    """
    query = db.query(TestTask).filter(TestTask.project_id == project_id)

    if status is not None:
        query = query.filter(TestTask.status == status)

    return query.count()
