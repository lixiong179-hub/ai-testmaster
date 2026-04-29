"""
权限工具模块

提供项目级别的权限验证功能，确保用户只能操作属于自己的项目。
当前实现为简单的属主校验（project.user_id == user_id），
后续可扩展为基于角色的访问控制（RBAC）。

核心函数：
    - verify_project_permission: 验证用户对项目的操作权限

依赖：
    - sqlalchemy.orm.Session: 数据库会话
    - app.models.project.Project: 项目数据模型
    - fastapi: HTTP异常响应
"""
from sqlalchemy.orm import Session
from app.models.project import Project
from fastapi import HTTPException, status


def verify_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    """验证用户是否有权限操作指定项目

    通过查询数据库确认项目存在且属于当前用户。
    验证失败时抛出403 Forbidden异常，不区分"项目不存在"和"无权限"，
    防止通过404/403差异推断项目ID是否有效（信息泄露防护）。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID

    Returns:
        Project: 验证通过的项目对象

    Raises:
        HTTPException: 当项目不存在或用户无权限时抛出403异常
    """
    # 同时过滤project_id和user_id，不区分不存在和无权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    
    return project
