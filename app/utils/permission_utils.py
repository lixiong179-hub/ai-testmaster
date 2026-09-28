"""
权限工具模块

提供项目级别的权限验证功能。校验顺序（向后兼容 + ProjectMember 集成）：
    1. 属主校验：project.user_id == user_id 直接通过（旧有语义）；
    2. 项目成员校验：user 是 ProjectMember 且角色层级 >= member 通过；
    3. 否则抛 403（不区分"项目不存在"和"无权限"，防止信息泄露）。

核心函数：
    - verify_project_permission: 同步验证用户对项目的操作权限
    - verify_project_permission_async: 异步验证用户对项目的操作权限

依赖：
    - sqlalchemy.orm.Session / sqlalchemy.ext.asyncio.AsyncSession
    - app.models.project.Project
    - app.models.project_member.ProjectMember, ROLE_LEVEL
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember, ROLE_LEVEL

# 项目成员校验的最低角色层级（member=2）
_MEMBER_MIN_LEVEL = ROLE_LEVEL.get("member", 2)


def _raise_forbidden() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="无权限操作此项目",
    )


def verify_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    """验证用户是否有权限操作指定项目（同步）。

    属主（project.user_id == user_id）或项目成员（role_level >= member）通过，
    否则抛 403。不区分"项目不存在"和"无权限"，防止信息泄露。

    Args:
        db: 同步数据库会话。
        project_id: 项目 ID。
        user_id: 用户 ID。

    Returns:
        Project: 验证通过的项目对象。

    Raises:
        HTTPException: 项目不存在或用户无权限时抛 403。
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        _raise_forbidden()

    # 旧有属主校验兜底
    if project.user_id == user_id:
        return project

    # 项目成员校验
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if member and ROLE_LEVEL.get(member.role, 0) >= _MEMBER_MIN_LEVEL:
        return project

    _raise_forbidden()


async def verify_project_permission_async(
    db: AsyncSession, project_id: int, user_id: int
) -> Project:
    """验证用户是否有权限操作指定项目（异步）。

    语义与同步版完全一致（属主或项目成员通过）。
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        _raise_forbidden()

    if project.user_id == user_id:
        return project

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if member and ROLE_LEVEL.get(member.role, 0) >= _MEMBER_MIN_LEVEL:
        return project

    _raise_forbidden()
