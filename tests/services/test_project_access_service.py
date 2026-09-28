"""ProjectAccessService 单元测试。

覆盖 app/services/project_access_service.py 的全部方法：
    - check_project_access (sync)        : 超管/owner/admin/member/viewer/非成员/角色不足
    - check_project_access_async (async) : 同上
    - get_user_role (sync)               : 成员/非成员
    - get_user_role_async (async)        : 成员/非成员
    - add_member (sync)                  : 成功/非法角色/重复成员

事务隔离：async_db / db fixture 外层事务包裹，结束 rollback 自动清理。
"""
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services.project_access_service import ProjectAccessService
from app.utils.jwt_utils import get_password_hash


# ============================================================================
# 测试数据辅助函数
# ============================================================================


async def _create_member(async_db, project_id, user_id, role="member"):
    """创建项目成员记录并 flush。"""
    member = ProjectMember(
        project_id=project_id, user_id=user_id, role=role,
    )
    async_db.add(member)
    await async_db.flush()
    return member


async def _create_other_user(async_db, *, is_superuser=False):
    """创建另一个用户并 flush，用于权限隔离测试。"""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"other_pas_{suffix}",
        email=f"other_pas_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=is_superuser,
    )
    async_db.add(user)
    await async_db.flush()
    return user


def _create_member_sync(db, project_id, user_id, role="member"):
    """创建项目成员记录并 flush（sync）。"""
    member = ProjectMember(
        project_id=project_id, user_id=user_id, role=role,
    )
    db.add(member)
    db.flush()
    return member


def _create_other_user_sync(db, *, is_superuser=False):
    """创建另一个用户并 flush（sync）。"""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"other_pas_{suffix}",
        email=f"other_pas_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


# ============================================================================
# check_project_access_async 测试
# ============================================================================


class TestCheckProjectAccessAsync:
    """check_project_access_async 异步权限校验。"""

    async def test_superuser_bypasses_check(
        self, async_db, async_test_project
    ):
        """超级管理员自动放行，返回虚拟 owner 成员。"""
        superuser = await _create_other_user(async_db, is_superuser=True)
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, superuser, "owner",
        )
        assert member.role == "owner"
        assert member.user_id == superuser.id

    async def test_owner_passes_owner_required(
        self, async_db, async_test_user, async_test_project
    ):
        """owner 角色通过 owner 级别校验。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "owner")
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, async_test_user, "owner",
        )
        assert member.role == "owner"

    async def test_admin_passes_member_required(
        self, async_db, async_test_user, async_test_project
    ):
        """admin 角色通过 member 级别校验。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "admin")
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, async_test_user, "member",
        )
        assert member.role == "admin"

    async def test_member_passes_member_required(
        self, async_db, async_test_user, async_test_project
    ):
        """member 角色通过 member 级别校验。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "member")
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, async_test_user, "member",
        )
        assert member.role == "member"

    async def test_viewer_fails_member_required(
        self, async_db, async_test_user, async_test_project
    ):
        """viewer 角色不满足 member 级别，抛 403。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "viewer")
        with pytest.raises(HTTPException) as exc_info:
            await ProjectAccessService.check_project_access_async(
                async_db, async_test_project.id, async_test_user, "member",
            )
        assert exc_info.value.status_code == 403
        assert "member" in exc_info.value.detail

    async def test_non_member_fails(
        self, async_db, async_test_user, async_test_project
    ):
        """非项目成员抛 403。"""
        other_user = await _create_other_user(async_db)
        with pytest.raises(HTTPException) as exc_info:
            await ProjectAccessService.check_project_access_async(
                async_db, async_test_project.id, other_user, "member",
            )
        assert exc_info.value.status_code == 403
        assert "无权限" in exc_info.value.detail

    async def test_viewer_passes_viewer_required(
        self, async_db, async_test_user, async_test_project
    ):
        """viewer 角色通过 viewer 级别校验（最低权限）。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "viewer")
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, async_test_user, "viewer",
        )
        assert member.role == "viewer"

    async def test_owner_passes_admin_required(
        self, async_db, async_test_user, async_test_project
    ):
        """owner 角色层级 > admin，通过 admin 级别校验。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "owner")
        member = await ProjectAccessService.check_project_access_async(
            async_db, async_test_project.id, async_test_user, "admin",
        )
        assert member.role == "owner"


# ============================================================================
# get_user_role_async 测试
# ============================================================================


class TestGetUserRoleAsync:
    """get_user_role_async 查询用户角色。"""

    async def test_returns_role_for_member(
        self, async_db, async_test_user, async_test_project
    ):
        """项目成员返回其角色。"""
        await _create_member(async_db, async_test_project.id, async_test_user.id, "admin")
        role = await ProjectAccessService.get_user_role_async(
            async_db, async_test_project.id, async_test_user.id,
        )
        assert role == "admin"

    async def test_returns_none_for_non_member(
        self, async_db, async_test_project
    ):
        """非成员返回 None。"""
        other_user = await _create_other_user(async_db)
        role = await ProjectAccessService.get_user_role_async(
            async_db, async_test_project.id, other_user.id,
        )
        assert role is None


# ============================================================================
# check_project_access (sync) 测试
# ============================================================================


class TestCheckProjectAccessSync:
    """check_project_access 同步权限校验。"""

    def test_superuser_bypasses_check(self, db, testProject):
        """超级管理员自动放行（sync）。"""
        superuser = _create_other_user_sync(db, is_superuser=True)
        member = ProjectAccessService.check_project_access(
            db, testProject.id, superuser, "owner",
        )
        assert member.role == "owner"

    def test_owner_passes(self, db, testUser, testProject):
        """owner 角色通过校验（sync）。"""
        _create_member_sync(db, testProject.id, testUser.id, "owner")
        member = ProjectAccessService.check_project_access(
            db, testProject.id, testUser, "owner",
        )
        assert member.role == "owner"

    def test_non_member_fails(self, db, testProject):
        """非成员抛 403（sync）。"""
        other_user = _create_other_user_sync(db)
        with pytest.raises(HTTPException) as exc_info:
            ProjectAccessService.check_project_access(
                db, testProject.id, other_user, "member",
            )
        assert exc_info.value.status_code == 403

    def test_insufficient_role_fails(self, db, testUser, testProject):
        """角色层级不足抛 403（sync）。"""
        _create_member_sync(db, testProject.id, testUser.id, "viewer")
        with pytest.raises(HTTPException) as exc_info:
            ProjectAccessService.check_project_access(
                db, testProject.id, testUser, "admin",
            )
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail


# ============================================================================
# get_user_role (sync) 测试
# ============================================================================


class TestGetUserRoleSync:
    """get_user_role 同步查询用户角色。"""

    def test_returns_role_for_member(self, db, testUser, testProject):
        """项目成员返回其角色（sync）。"""
        _create_member_sync(db, testProject.id, testUser.id, "member")
        role = ProjectAccessService.get_user_role(
            db, testProject.id, testUser.id,
        )
        assert role == "member"

    def test_returns_none_for_non_member(self, db, testProject):
        """非成员返回 None（sync）。"""
        other_user = _create_other_user_sync(db)
        role = ProjectAccessService.get_user_role(
            db, testProject.id, other_user.id,
        )
        assert role is None


# ============================================================================
# add_member (sync) 测试
# ============================================================================


class TestAddMemberSync:
    """add_member 添加项目成员。"""

    def test_add_member_success(self, db, testUser, testProject):
        """成功添加成员。"""
        other_user = _create_other_user_sync(db)
        member = ProjectAccessService.add_member(
            db, testProject.id, other_user.id, "member",
        )
        assert member.project_id == testProject.id
        assert member.user_id == other_user.id
        assert member.role == "member"

    def test_add_member_invalid_role(self, db, testProject):
        """非法角色抛 400。"""
        other_user = _create_other_user_sync(db)
        with pytest.raises(HTTPException) as exc_info:
            ProjectAccessService.add_member(
                db, testProject.id, other_user.id, "super_admin",
            )
        assert exc_info.value.status_code == 400
        assert "非法角色" in exc_info.value.detail

    def test_add_member_duplicate(self, db, testUser, testProject):
        """重复成员抛 400。"""
        _create_member_sync(db, testProject.id, testUser.id, "owner")
        with pytest.raises(HTTPException) as exc_info:
            ProjectAccessService.add_member(
                db, testProject.id, testUser.id, "member",
            )
        assert exc_info.value.status_code == 400
        assert "成员已存在" in exc_info.value.detail

    def test_add_member_default_role(self, db, testProject):
        """未指定角色时默认 member。"""
        other_user = _create_other_user_sync(db)
        member = ProjectAccessService.add_member(
            db, testProject.id, other_user.id,
        )
        assert member.role == "member"
