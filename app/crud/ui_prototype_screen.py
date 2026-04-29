"""
UI原型页面查询操作模块

提供UI原型页面（UIPrototypeScreen）的所有只读查询操作，与 ui_prototype_screen_mutate.py
共同构成UI原型页面的完整CRUD能力。本模块仅包含查询函数，不涉及任何数据变更。

核心函数概览：
    - _apply_iteration_filter: 迭代过滤条件构建器（内部函数，被多个查询复用）
    - get_ui_screen_by_id: 根据ID获取UI页面（可选项目隔离）
    - get_ui_screens_by_project: 获取项目的UI页面列表（多条件动态过滤+迭代过滤+排序+分页）
    - get_ui_screens_count: 获取UI页面数量（用于分页计算）
    - get_test_cases_by_screen: 获取页面关联的测试用例ID列表
    - get_parsed_ui_screens_for_case_generation: 获取已解析的UI页面（用于AI用例生成）

与Model/Schema的对应关系：
    - Model: app.models.ui_prototype.UIPrototypeScreen
    - Model: app.models.ui_prototype.UIScreenTestCaseLink（页面-用例关联表）
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）
    - 关联Model: app.models.ui_prototype.UIPrototypeProject（迭代过滤JOIN）

查询条件构建逻辑：
    - 动态过滤：根据可选参数（prototype_project_id/parse_status/iteration_id）逐步追加filter
    - 权限隔离：通过JOIN Project表确保用户只能查询自己项目下的页面
    - 迭代过滤：通过_apply_iteration_filter函数统一处理，支持-1特殊值
    - 排序：先按screen_order排序，再按create_time排序，确保页面顺序可控

性能考虑：
    - _apply_iteration_filter 使用outerjoin处理-1（未关联迭代）的情况，
      因为页面可能没有关联的原型项目
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.ui_prototype import (
    UIPrototypeScreen,
    UIScreenTestCaseLink,
)
from app.models.project import Project
from app.utils.db_time import utcnow


def _apply_iteration_filter(query: Any, iteration_id: Optional[int]) -> Any:
    """
    迭代过滤条件构建器（内部函数）

    根据iteration_id参数动态构建迭代过滤条件。此函数被多个查询函数复用，
    统一处理迭代过滤逻辑。

    过滤逻辑：
    - iteration_id=None: 不追加任何过滤条件
    - iteration_id=-1: 使用outerjoin查询未关联迭代的页面
      （UIPrototypeProject.iteration_id IS NULL 或页面无关联原型项目）
    - iteration_id=其他值: 使用join查询指定迭代下的页面

    Args:
        query: SQLAlchemy查询对象
        iteration_id: 迭代ID，None表示不过滤，-1表示未关联迭代

    Returns:
        追加迭代过滤条件后的查询对象

    Note:
        - iteration_id=-1时使用outerjoin而非join，因为页面可能没有关联原型项目
        - 使用 or_ 条件同时处理"原型项目无迭代"和"页面无原型项目"两种情况
    """
    from app.models.ui_prototype import UIPrototypeProject
    if iteration_id is not None:
        if iteration_id == -1:
            # 查询未关联迭代的页面：使用outerjoin保留无原型项目的页面
            query = query.outerjoin(
                UIPrototypeProject,
                UIPrototypeScreen.prototype_project_id == UIPrototypeProject.id,
            ).filter(
                or_(
                    UIPrototypeProject.iteration_id.is_(None),  # 原型项目无迭代
                    UIPrototypeScreen.prototype_project_id.is_(None),  # 页面无原型项目
                )
            )
        else:
            # 查询指定迭代下的页面：使用join确保原型项目存在
            query = query.join(
                UIPrototypeProject,
                UIPrototypeScreen.prototype_project_id == UIPrototypeProject.id,
            ).filter(UIPrototypeProject.iteration_id == iteration_id)
    return query


def get_ui_screen_by_id(
    db: Session, screen_id: int, project_id: Optional[int] = None
) -> Optional[UIPrototypeScreen]:
    """
    根据ID获取UI页面

    支持可选的项目ID过滤，传入project_id时增加项目维度隔离校验。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        project_id: 项目ID（可选），用于隔离校验

    Returns:
        Optional[UIPrototypeScreen]: 页面对象，不存在则返回None
    """
    query = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id)
    if project_id:
        query = query.filter(UIPrototypeScreen.project_id == project_id)
    return query.first()


def get_ui_screens_by_project(
    db: Session,
    project_id: int,
    user_id: int,
    prototype_project_id: Optional[int] = None,
    parse_status: Optional[str] = None,
    iteration_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[UIPrototypeScreen]:
    """
    获取项目的UI页面列表（多条件动态过滤+迭代过滤+排序+分页）

    通过JOIN Project表实现用户权限隔离，支持按原型项目、解析状态、迭代等
    多维度动态过滤。排序策略为先按screen_order排序，再按创建时间排序。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离
        prototype_project_id: 原型项目ID（可选），按原型项目过滤
        parse_status: 解析状态（可选），pending/completed/failed
        iteration_id: 迭代ID（可选），-1表示未关联迭代
        skip: 跳过记录数
        limit: 返回记录上限

    Returns:
        List[UIPrototypeScreen]: UI页面列表，按screen_order和create_time排序
    """
    # JOIN Project表：通过Project.user_id实现用户权限隔离
    query = (
        db.query(UIPrototypeScreen)
        .join(Project)
        .filter(UIPrototypeScreen.project_id == project_id, Project.user_id == user_id)
    )
    # 动态追加过滤条件
    if prototype_project_id:
        query = query.filter(UIPrototypeScreen.prototype_project_id == prototype_project_id)
    if parse_status:
        query = query.filter(UIPrototypeScreen.parse_status == parse_status)
    # 迭代过滤：复用_apply_iteration_filter统一处理
    query = _apply_iteration_filter(query, iteration_id)
    # 排序：先按screen_order排序（用户自定义顺序），再按创建时间排序
    return query.order_by(
        UIPrototypeScreen.screen_order, UIPrototypeScreen.create_time
    ).offset(skip).limit(limit).all()


def get_ui_screens_count(
    db: Session,
    project_id: int,
    user_id: int,
    prototype_project_id: Optional[int] = None,
    parse_status: Optional[str] = None,
    iteration_id: Optional[int] = None,
) -> int:
    """
    获取UI页面数量

    用于分页计算总条数，查询条件与 get_ui_screens_by_project 一致。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        prototype_project_id: 原型项目ID（可选）
        parse_status: 解析状态（可选）
        iteration_id: 迭代ID（可选）

    Returns:
        int: 符合条件的页面数量
    """
    query = (
        db.query(UIPrototypeScreen)
        .join(Project)
        .filter(UIPrototypeScreen.project_id == project_id, Project.user_id == user_id)
    )
    if prototype_project_id:
        query = query.filter(UIPrototypeScreen.prototype_project_id == prototype_project_id)
    if parse_status:
        query = query.filter(UIPrototypeScreen.parse_status == parse_status)
    query = _apply_iteration_filter(query, iteration_id)
    return query.count()


def get_test_cases_by_screen(db: Session, screen_id: int) -> List[int]:
    """
    获取页面关联的测试用例ID列表

    通过UIScreenTestCaseLink关联表查询页面关联的所有测试用例ID。
    用于展示页面与用例的追溯关系。

    Args:
        db: 数据库会话
        screen_id: 页面ID

    Returns:
        List[int]: 关联的测试用例ID列表

    Note:
        此函数未做权限过滤，调用方需自行校验访问权限。
    """
    links = db.query(UIScreenTestCaseLink).filter(
        UIScreenTestCaseLink.screen_id == screen_id
    ).all()
    return [link.test_case_id for link in links]


def get_parsed_ui_screens_for_case_generation(
    db: Session,
    project_id: int,
    user_id: int,
    prototype_project_id: Optional[int] = None,
    approved_only: bool = True,
) -> List[UIPrototypeScreen]:
    """
    获取已解析的UI页面（用于AI用例生成）

    查询解析完成（parse_status=completed）的页面，可选仅返回已审核通过的页面。
    主要用于AI生成测试用例时获取UI页面信息。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离
        prototype_project_id: 原型项目ID（可选），按原型项目过滤
        approved_only: 是否仅返回已审核的页面，默认True。
            True: 返回审核通过(approved)或待审核(pending)的页面
            False: 返回所有已解析的页面（包括被拒绝的）

    Returns:
        List[UIPrototypeScreen]: 已解析的UI页面列表，按screen_order和create_time排序

    Note:
        approved_only=True时，使用 or_ 条件同时包含approved和pending状态，
        因为pending状态的页面尚未被拒绝，也应参与用例生成。
    """
    query = (
        db.query(UIPrototypeScreen)
        .join(Project)
        .filter(
            UIPrototypeScreen.project_id == project_id,
            Project.user_id == user_id,
            UIPrototypeScreen.parse_status == "completed",  # 仅查询解析完成的页面
        )
    )
    if prototype_project_id:
        query = query.filter(UIPrototypeScreen.prototype_project_id == prototype_project_id)
    if approved_only:
        # 包含approved和pending状态，排除rejected状态
        query = query.filter(
            or_(
                UIPrototypeScreen.review_status == "approved",
                UIPrototypeScreen.review_status == "pending",
            )
        )
    return query.order_by(
        UIPrototypeScreen.screen_order, UIPrototypeScreen.create_time
    ).all()
