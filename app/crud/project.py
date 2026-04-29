"""
项目CRUD操作模块

提供项目（Project）的增删改查数据库操作，是系统最基础的数据隔离单元。
所有业务实体（测试用例、测试点、测试任务等）均以项目为顶层归属。

核心函数概览：
    - create_project: 创建项目，默认状态为启用(1)
    - get_projects: 获取用户的所有项目（分页）
    - get_project_by_id: 根据ID获取项目（带用户权限过滤）
    - update_project: 更新项目信息（仅更新传入字段）
    - delete_project: 硬删除项目（带用户权限过滤）

与Model/Schema的对应关系：
    - Model: app.models.project.Project
    - Create Schema: app.schemas.project.ProjectCreate
    - Update Schema: app.schemas.project.ProjectUpdate

事务处理方式：
    - 所有写操作（create/update/delete）均自动commit
    - 无需调用方手动管理事务

注意：删除为硬删除，会物理移除数据库记录，关联数据需在调用方处理级联清理。
"""
from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from typing import List, Optional


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
