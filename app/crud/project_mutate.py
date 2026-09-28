"""
项目变更操作模块

提供项目（Project）的所有变更操作（创建/更新/删除），
与 project_query.py 共同构成项目的完整CRUD能力。
本模块仅包含变更函数，不涉及对外暴露的查询操作。

核心函数概览：
    - create_project: 创建项目，默认状态为启用(1)
    - update_project: 更新项目信息（仅更新传入字段，带用户权限过滤）
    - delete_project: 硬删除项目（带用户权限过滤）

与Model/Schema的对应关系：
    - Model: app.models.project.Project
    - Create Schema: app.schemas.project.ProjectCreate
    - Update Schema: app.schemas.project.ProjectUpdate

依赖关系：
    - 复用 project_query.get_project_by_id 作为 update/delete 的权限校验前置检查

事务处理方式：
    - 所有写操作均自动 commit，无需调用方手动管理事务

软删除/硬删除：
    - delete_project 为硬删除，物理移除数据库记录
    - 关联数据需在调用方处理级联清理，否则可能产生孤立数据
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.crud.project_query import get_project_by_id


def create_project(db: Session, project: ProjectCreate, user_id: int) -> Project:
    """
    创建项目

    创建一个新的测试项目，默认状态为启用(1)。项目是系统中最顶层的数据隔离单元，
    后续的测试用例、测试点、测试任务等均归属于项目。

    Args:
        db: 数据库会话，由依赖注入提供
        project: 项目创建参数，包含name/description/project_type
        user_id: 创建者用户ID，用于数据隔离，确保用户只能访问自己的项目

    Returns:
        Project: 创建成功后的项目对象（已commit并refresh，含数据库生成的id和默认值）

    Raises:
        无显式异常，依赖SQLAlchemy的数据库约束（如唯一性约束）
    """
    db_project = Project(
        name=project.name,
        description=project.description,
        user_id=user_id,
        status=1,  # 默认状态为启用：1=启用, 0=禁用
        project_type=project.project_type
    )
    db.add(db_project)
    db.commit()  # 自动提交事务
    db.refresh(db_project)  # 刷新以获取数据库生成的字段（如id、create_time）
    return db_project


def update_project(db: Session, project_id: int, project_update: ProjectUpdate, user_id: int) -> Optional[Project]:
    """
    更新项目，带用户权限过滤

    仅更新传入的非空字段（exclude_unset=True），未传入的字段保持原值不变。
    先通过 get_project_by_id 校验用户权限，无权限则返回None。

    Args:
        db: 数据库会话
        project_id: 待更新的项目ID
        project_update: 项目更新参数，仅包含需要修改的字段
        user_id: 用户ID，用于权限校验

    Returns:
        Optional[Project]: 更新后的项目对象，若项目不存在或无权限则返回None

    Note:
        使用 model_dump(exclude_unset=True) 实现"部分更新"语义，
        避免未传入字段被覆盖为None。
    """
    db_project = get_project_by_id(db, project_id, user_id)
    if not db_project:
        return None

    # exclude_unset=True: 仅获取用户实际传入的字段，未传入的字段不会出现在update_data中
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)

    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: int, user_id: int) -> bool:
    """
    删除项目，带用户权限过滤（硬删除）

    物理删除项目记录，数据库中不再保留。删除前通过 get_project_by_id
    校验用户权限。

    Args:
        db: 数据库会话
        project_id: 待删除的项目ID
        user_id: 用户ID，用于权限校验

    Returns:
        bool: 删除成功返回True，项目不存在或无权限返回False

    Warning:
        此为硬删除操作，会物理移除数据库记录。关联的测试用例、测试点等
        数据需在调用方处理级联清理，否则可能产生孤立数据。
    """
    db_project = get_project_by_id(db, project_id, user_id)
    if not db_project:
        return False

    db.delete(db_project)  # 硬删除：物理移除数据库记录
    db.commit()
    return True
