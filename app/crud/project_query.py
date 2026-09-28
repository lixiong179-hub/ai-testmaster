"""
项目查询操作模块

提供项目（Project）的所有只读查询操作，与 project_mutate.py 共同构成
项目的完整CRUD能力。本模块仅包含查询函数，不涉及任何数据变更。

核心函数概览：
    - get_projects: 获取用户的所有项目（分页）
    - get_project_by_id: 根据ID获取项目（带用户权限过滤）

与Model/Schema的对应关系：
    - Model: app.models.project.Project

权限隔离设计：
    - 所有查询均通过 user_id 过滤，实现多租户数据隔离
    - get_project_by_id 同时按 project_id 和 user_id 过滤，
      防止越权访问其他用户的项目数据
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.project import Project


def get_projects(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Project]:
    """
    获取用户的所有项目（分页）

    按用户ID过滤项目列表，实现多租户数据隔离。结果按默认排序返回。

    Args:
        db: 数据库会话
        user_id: 用户ID，用于数据隔离过滤
        skip: 跳过记录数，用于分页偏移，默认0
        limit: 返回记录上限，默认100，防止一次性加载过多数据

    Returns:
        List[Project]: 该用户的项目列表，可能为空列表

    Note:
        未指定排序字段，依赖数据库默认排序。如需按创建时间倒序，
        可追加 .order_by(Project.create_time.desc())
    """
    return db.query(Project).filter(Project.user_id == user_id).offset(skip).limit(limit).all()


def get_project_by_id(db: Session, project_id: int, user_id: int) -> Optional[Project]:
    """
    根据ID获取项目，带用户权限过滤

    同时按项目ID和用户ID进行过滤，确保用户只能访问自己拥有的项目，
    防止越权访问其他用户的项目数据。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，用于权限校验

    Returns:
        Optional[Project]: 项目对象，若不存在或不属于该用户则返回None

    Note:
        此函数被 update_project 和 delete_project 复用，作为权限校验的前置检查。
    """
    return db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
