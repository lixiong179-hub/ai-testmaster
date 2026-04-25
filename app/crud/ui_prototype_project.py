"""
UI原型项目CRUD操作模块

提供UI原型项目（UIPrototypeProject）的增删改查数据库操作。UI原型项目是
墨刀等设计工具导出的原型集合，包含多个页面（Screen），支持解析状态跟踪、
统计信息聚合、合并流程图等。

核心函数概览：
    - create_ui_prototype_project: 创建UI原型项目
    - get_ui_prototype_projects_by_project: 获取项目的UI原型项目列表（JOIN权限隔离+迭代过滤）
    - get_ui_prototype_projects_count: 获取UI原型项目数量
    - update_prototype_project_stats: 更新原型项目统计信息（页面数/解析数/解析状态）
    - update_prototype_project_merged_flow: 更新原型项目的合并流程图

与Model/Schema的对应关系：
    - Model: app.models.ui_prototype.UIPrototypeProject
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）
    - 关联Model: app.models.ui_prototype.UIPrototypeScreen（统计信息聚合查询）

与其他CRUD模块的调用关系：
    - UI原型项目包含多个UIPrototypeScreen（一对多）
    - 页面解析完成后调用 update_prototype_project_stats 更新统计信息
    - 流程合并后调用 update_prototype_project_merged_flow 更新合并流程

事务处理方式：
    - 所有写操作均自动commit

迭代过滤约定：
    - iteration_id=None（显式传入）：查询未关联迭代的记录（iteration_id IS NULL）
    - iteration_id=正整数：按迭代ID精确匹配
    - 不传 iteration_id：不过滤迭代
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.ui_prototype import UIPrototypeProject
from app.models.project import Project
from app.utils.db_time import utcnow


def create_ui_prototype_project(
    db: Session,
    project_id: int,
    name: str,
    created_by: Optional[int] = None,
    description: Optional[str] = None,
    source: str = "mockingbot",
    iteration_id: Optional[int] = None,
) -> UIPrototypeProject:
    """
    创建UI原型项目

    创建一个新的UI原型项目记录，默认来源为墨刀（mockingbot）。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        name: 原型项目名称
        created_by: 创建者用户ID（可选）
        description: 原型项目描述（可选）
        source: 原型来源，默认"mockingbot"（墨刀），可扩展其他设计工具
        iteration_id: 关联迭代ID（可选），用于按迭代管理原型

    Returns:
        UIPrototypeProject: 创建成功后的原型项目对象（已commit并refresh）
    """
    db_project = UIPrototypeProject(
        project_id=project_id,
        name=name,
        description=description,
        source=source,
        created_by=created_by,
        iteration_id=iteration_id,
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_ui_prototype_projects_by_project(
    db: Session,
    project_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    iteration_id: Optional[int] = None,
) -> List[UIPrototypeProject]:
    """
    获取项目的UI原型项目列表（JOIN权限隔离+迭代过滤）

    通过JOIN Project表实现用户权限隔离，支持按迭代ID过滤。
    支持显式传入 iteration_id=None 查询未关联迭代的记录。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离
        skip: 跳过记录数
        limit: 返回记录上限
        iteration_id: 迭代ID（可选），None表示查询未关联迭代的记录，正整数按迭代ID匹配

    Returns:
        List[UIPrototypeProject]: UI原型项目列表
    """
    query = (
        db.query(UIPrototypeProject)
        .join(Project)
        .filter(
            UIPrototypeProject.project_id == project_id,
            Project.user_id == user_id,
        )
    )
    # 迭代过滤：None表示未关联迭代的记录，正整数按迭代ID精确匹配
    if iteration_id is not None:
        if iteration_id <= 0:
            # 兼容旧调用：<=0 的值统一视为"未关联迭代"，查询 IS NULL
            query = query.filter(UIPrototypeProject.iteration_id.is_(None))
        else:
            query = query.filter(
                UIPrototypeProject.iteration_id == iteration_id
            )
    return query.offset(skip).limit(limit).all()


def get_ui_prototype_projects_count(
    db: Session,
    project_id: int,
    user_id: int,
    iteration_id: Optional[int] = None,
) -> int:
    """
    获取UI原型项目数量

    用于分页计算总条数，查询条件与 get_ui_prototype_projects_by_project 一致。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        iteration_id: 迭代ID（可选）

    Returns:
        int: 原型项目数量
    """
    query = (
        db.query(UIPrototypeProject)
        .join(Project)
        .filter(
            UIPrototypeProject.project_id == project_id,
            Project.user_id == user_id,
        )
    )
    if iteration_id is not None:
        if iteration_id <= 0:
            # 兼容旧调用：<=0 的值统一视为"未关联迭代"，查询 IS NULL
            query = query.filter(UIPrototypeProject.iteration_id.is_(None))
        else:
            query = query.filter(
                UIPrototypeProject.iteration_id == iteration_id
            )
    return query.count()


def update_prototype_project_stats(
    db: Session, prototype_project_id: int
) -> Optional[UIPrototypeProject]:
    """
    更新原型项目统计信息

    根据关联页面的实际状态，重新计算并更新原型项目的统计字段：
    - screen_count: 页面总数
    - parsed_count: 已解析页面数
    - parse_status: 解析状态（pending/partial/completed）

    此函数应在页面解析状态变更后调用，确保统计信息与实际数据一致。

    Args:
        db: 数据库会话
        prototype_project_id: 原型项目ID

    Returns:
        Optional[UIPrototypeProject]: 更新后的原型项目对象，不存在则返回None

    Note:
        解析状态计算逻辑：
        - parsed_count=0 -> pending（尚未开始解析）
        - parsed_count=screen_count -> completed（全部解析完成）
        - 其他 -> partial（部分解析完成）
    """
    from sqlalchemy import case, func, Integer
    from app.models.ui_prototype import UIPrototypeScreen

    project = (
        db.query(UIPrototypeProject)
        .filter(UIPrototypeProject.id == prototype_project_id)
        .first()
    )
    if not project:
        return None

    stats = db.query(
        func.count(UIPrototypeScreen.id).label('total'),
        func.sum(
            case(
                (UIPrototypeScreen.parse_status == 'completed', 1),
                else_=0
            )
        ).label('parsed')
    ).filter(
        UIPrototypeScreen.prototype_project_id == prototype_project_id
    ).first()

    project.screen_count = stats.total or 0
    project.parsed_count = stats.parsed or 0

    if project.parsed_count == 0:
        project.parse_status = "pending"
    elif project.parsed_count == project.screen_count:
        project.parse_status = "completed"
    else:
        project.parse_status = "partial"
    project.update_time = utcnow()
    db.commit()
    db.refresh(project)
    return project


def update_prototype_project_merged_flow(
    db: Session, prototype_project_id: int, merged_flow: Dict[str, Any]
) -> Optional[UIPrototypeProject]:
    """
    更新原型项目的合并流程图

    将各页面的导航流程合并为整体流程图，用于全局导航分析和测试路径生成。

    Args:
        db: 数据库会话
        prototype_project_id: 原型项目ID
        merged_flow: 合并后的流程图数据，JSON格式

    Returns:
        Optional[UIPrototypeProject]: 更新后的原型项目对象，不存在则返回None
    """
    project = (
        db.query(UIPrototypeProject)
        .filter(UIPrototypeProject.id == prototype_project_id)
        .first()
    )
    if not project:
        return None
    project.merged_flow = merged_flow
    project.update_time = utcnow()
    db.commit()
    db.refresh(project)
    return project
