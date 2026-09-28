"""项目访问控制服务 - 基于 ProjectMember 表的权限校验。

替代原有 app/utils/permission_utils.py 的单一属主校验（project.user_id == user_id），
通过查询 project_members 表实现 owner/admin/member/viewer 四级角色权限控制。

核心类:
    - ProjectAccessService: 提供 sync + async 双模式的权限校验

权限层级（ROLE_LEVEL）:
    owner(4) > admin(3) > member(2) > viewer(1)

校验语义:
    - check_project_access(required_role): 用户角色层级 >= required_role 即通过
    - 超级管理员(is_superuser=True)自动放行
    - 非成员返回 403（不区分"非成员"和"项目不存在"，防信息泄露）

依赖:
    - app.models.project_member.ProjectMember, ROLE_LEVEL
    - app.models.user.User

使用场景:
    - sync 端点：ProjectAccessService.check_project_access(db, project_id, user, "member")
    - async 端点：await ProjectAccessService.check_project_access_async(db, project_id, user, "member")
"""
from __future__ import annotations

from typing import Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_member import ProjectMember, ROLE_LEVEL
from app.models.user import User


class ProjectAccessService:
    """项目访问控制服务 - 基于 ProjectMember 表的多角色权限校验。

    所有方法均为静态方法，支持 sync 和 async 两种调用模式。
    超级管理员自动绕过所有检查。
    """

    @staticmethod
    def check_project_access(
        db: Session,
        project_id: int,
        user: User,
        required_role: str = "member",
    ) -> ProjectMember:
        """校验用户对项目的访问权限（sync 模式）。

        Args:
            db: 同步数据库会话。
            project_id: 项目 ID。
            user: 当前用户对象。
            required_role: 所需最低角色层级，默认 "member"。

        Returns:
            ProjectMember: 校验通过的成员记录。

        Raises:
            HTTPException(403): 用户非成员或角色层级不足。
        """
        if getattr(user, "is_superuser", False):
            return _build_superuser_member(project_id, user.id)

        member = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        ).scalar_one_or_none()

        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目",
            )

        if not _has_sufficient_role(member.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {required_role} 或更高角色权限",
            )

        return member

    @staticmethod
    async def check_project_access_async(
        db: AsyncSession,
        project_id: int,
        user: User,
        required_role: str = "member",
    ) -> ProjectMember:
        """校验用户对项目的访问权限（async 模式）。

        Args:
            db: 异步数据库会话。
            project_id: 项目 ID。
            user: 当前用户对象。
            required_role: 所需最低角色层级，默认 "member"。

        Returns:
            ProjectMember: 校验通过的成员记录。

        Raises:
            HTTPException(403): 用户非成员或角色层级不足。
        """
        if getattr(user, "is_superuser", False):
            return _build_superuser_member(project_id, user.id)

        result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
        member = result.scalar_one_or_none()

        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目",
            )

        if not _has_sufficient_role(member.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {required_role} 或更高角色权限",
            )

        return member

    @staticmethod
    def get_user_role(
        db: Session, project_id: int, user_id: int
    ) -> Optional[str]:
        """查询用户在项目中的角色（sync 模式）。

        Returns:
            角色字符串（owner/admin/member/viewer），非成员返回 None。
        """
        member = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        ).scalar_one_or_none()
        return member.role if member else None

    @staticmethod
    async def get_user_role_async(
        db: AsyncSession, project_id: int, user_id: int
    ) -> Optional[str]:
        """查询用户在项目中的角色（async 模式）。

        Returns:
            角色字符串（owner/admin/member/viewer），非成员返回 None。
        """
        result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member else None

    @staticmethod
    def add_member(
        db: Session, project_id: int, user_id: int, role: str = "member"
    ) -> ProjectMember:
        """添加项目成员（sync 模式）。

        Args:
            db: 同步数据库会话。
            project_id: 项目 ID。
            user_id: 用户 ID。
            role: 成员角色，默认 "member"。

        Returns:
            ProjectMember: 创建的成员记录。

        Raises:
            HTTPException(400): 角色非法或成员已存在。
        """
        if not ProjectMember.is_valid_role(role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"非法角色: {role}",
            )

        existing = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="成员已存在",
            )

        member = ProjectMember(
            project_id=project_id, user_id=user_id, role=role,
        )
        db.add(member)
        db.flush()
        return member


def _has_sufficient_role(user_role: str, required_role: str) -> bool:
    """判断用户角色层级是否 >= 所需角色层级。"""
    user_level = ROLE_LEVEL.get(user_role, 0)
    required_level = ROLE_LEVEL.get(required_role, 0)
    return user_level >= required_level


def _build_superuser_member(project_id: int, user_id: Optional[int]) -> ProjectMember:
    """为超级管理员构造虚拟 owner 成员记录（不落库）。"""
    return ProjectMember(
        project_id=project_id, user_id=user_id or 0, role="owner",
    )


__all__ = ["ProjectAccessService"]
