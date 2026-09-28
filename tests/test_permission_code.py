"""权限码体系与项目成员模型测试。

覆盖：
    - PermissionCode 常量完整性（工作流B Task 7）
    - require_permission / require_project_role 依赖工厂可调用性
    - ProjectMember 模型方法（is_valid_role / role_level / to_dict）
    - verify_project_permission 向后兼容（ProjectMember + 旧有属主校验）

事务隔离：db / async_db fixture 外层事务包裹，结束 rollback 自动清理。
"""
import uuid

import pytest
from fastapi import HTTPException

# 先导入 app.main 触发完整应用初始化，避免 app.core.permissions 的循环导入
import app.main  # noqa: F401
from app.core.permissions import (
    PermissionCode,
    require_permission,
    require_project_role,
)
from app.models.project_member import ProjectMember, ROLE_LEVEL, VALID_ROLES
from app.models.user import User
from app.utils.jwt_utils import get_password_hash
from app.utils.permission_utils import (
    verify_project_permission,
    verify_project_permission_async,
)


# ============================================================================
# PermissionCode 常量测试
# ============================================================================


class TestPermissionCode:
    """权限码常量定义完整性。"""

    def test_project_codes_exist(self):
        """项目管理权限码已定义。"""
        assert PermissionCode.PROJECT_CREATE == "project:create"
        assert PermissionCode.PROJECT_READ == "project:read"
        assert PermissionCode.PROJECT_UPDATE == "project:update"
        assert PermissionCode.PROJECT_DELETE == "project:delete"
        assert PermissionCode.PROJECT_MEMBER_MANAGE == "project:member:manage"

    def test_test_case_codes_exist(self):
        """测试用例权限码已定义。"""
        assert PermissionCode.TEST_CASE_CREATE == "test_case:create"
        assert PermissionCode.TEST_CASE_READ == "test_case:read"
        assert PermissionCode.TEST_CASE_UPDATE == "test_case:update"
        assert PermissionCode.TEST_CASE_DELETE == "test_case:delete"
        assert PermissionCode.TEST_CASE_EXECUTE == "test_case:execute"

    def test_test_task_codes_exist(self):
        """测试任务与报告权限码已定义。"""
        assert PermissionCode.TEST_TASK_CREATE == "test_task:create"
        assert PermissionCode.TEST_TASK_READ == "test_task:read"
        assert PermissionCode.TEST_REPORT_READ == "test_report:read"
        assert PermissionCode.TEST_REPORT_EXPORT == "test_report:export"

    def test_agent_mcp_codes_exist(self):
        """Agent 与 MCP 权限码已定义。"""
        assert PermissionCode.AGENT_RUN == "agent:run"
        assert PermissionCode.MCP_READ == "mcp:read"
        assert PermissionCode.MCP_WRITE == "mcp:write"

    def test_self_healing_codes_exist(self):
        """自愈权限码已定义。"""
        assert PermissionCode.SELF_HEALING_READ == "self_healing:read"
        assert PermissionCode.SELF_HEALING_APPROVE == "self_healing:approve"

    def test_all_codes_follow_naming_convention(self):
        """所有权限码遵循 <资源>:<操作> 命名规范。"""
        codes = [
            attr for attr in dir(PermissionCode)
            if not attr.startswith("_") and isinstance(getattr(PermissionCode, attr), str)
        ]
        for code_attr in codes:
            code = getattr(PermissionCode, code_attr)
            assert ":" in code, f"权限码 {code_attr}={code} 缺少 ':' 分隔符"


# ============================================================================
# require_permission / require_project_role 工厂测试
# ============================================================================


class TestPermissionFactories:
    """权限校验依赖项工厂。"""

    def test_require_permission_returns_callable(self):
        """require_permission 返回可调用函数。"""
        checker = require_permission(PermissionCode.PROJECT_CREATE)
        assert callable(checker)

    def test_require_project_role_returns_callable(self):
        """require_project_role 返回可调用函数。"""
        checker = require_project_role("member")
        assert callable(checker)

    def test_require_project_role_default_member(self):
        """require_project_role 默认 required_role='member'。"""
        checker = require_project_role()
        assert callable(checker)


# ============================================================================
# ProjectMember 模型方法测试
# ============================================================================


class TestProjectMemberModel:
    """ProjectMember 模型方法。"""

    def test_is_valid_role_valid(self):
        """合法角色返回 True。"""
        for role in VALID_ROLES:
            assert ProjectMember.is_valid_role(role) is True

    def test_is_valid_role_invalid(self):
        """非法角色返回 False。"""
        assert ProjectMember.is_valid_role("super_admin") is False
        assert ProjectMember.is_valid_role("") is False
        assert ProjectMember.is_valid_role("guest") is False

    def test_role_level_returns_correct_value(self):
        """role_level 返回正确的层级数值。"""
        assert ProjectMember.role_level("viewer") == 1
        assert ProjectMember.role_level("member") == 2
        assert ProjectMember.role_level("admin") == 3
        assert ProjectMember.role_level("owner") == 4

    def test_role_level_invalid_returns_zero(self):
        """非法角色返回 0。"""
        assert ProjectMember.role_level("invalid") == 0
        assert ProjectMember.role_level("") == 0

    def test_role_level_hierarchy(self):
        """角色层级 owner > admin > member > viewer。"""
        assert ROLE_LEVEL["owner"] > ROLE_LEVEL["admin"]
        assert ROLE_LEVEL["admin"] > ROLE_LEVEL["member"]
        assert ROLE_LEVEL["member"] > ROLE_LEVEL["viewer"]

    def test_to_dict_returns_all_fields(self, db, testUser, testProject):
        """to_dict 返回所有字段。"""
        member = ProjectMember(
            project_id=testProject.id, user_id=testUser.id, role="admin",
        )
        db.add(member)
        db.flush()
        d = member.to_dict()
        assert d["project_id"] == testProject.id
        assert d["user_id"] == testUser.id
        assert d["role"] == "admin"
        assert "id" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_repr_returns_string(self, db, testUser, testProject):
        """__repr__ 返回字符串表示。"""
        member = ProjectMember(
            project_id=testProject.id, user_id=testUser.id, role="member",
        )
        db.add(member)
        db.flush()
        repr_str = repr(member)
        assert "ProjectMember" in repr_str
        assert "member" in repr_str
        assert str(testProject.id) in repr_str


# ============================================================================
# verify_project_permission 测试（向后兼容）
# ============================================================================


class TestVerifyProjectPermissionBackwardCompat:
    """verify_project_permission 向后兼容测试。"""

    def test_legacy_owner_passes(self, db, testUser, testProject):
        """旧有属主校验：project.user_id == user_id 时通过。"""
        project = verify_project_permission(db, testProject.id, testUser.id)
        assert project.id == testProject.id

    def test_non_owner_fails(self, db, testProject):
        """非属主用户抛 403。"""
        suffix = uuid.uuid4().hex[:8]
        other_user = User(
            username=f"noperm_{suffix}",
            email=f"noperm_{suffix}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        with pytest.raises(HTTPException) as exc_info:
            verify_project_permission(db, testProject.id, other_user.id)
        assert exc_info.value.status_code == 403

    def test_project_member_passes(self, db, testUser, testProject):
        """ProjectMember 成员通过新权限体系校验。"""
        other_user = User(
            username=f"member_{uuid.uuid4().hex[:8]}",
            email=f"member_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        member = ProjectMember(
            project_id=testProject.id, user_id=other_user.id, role="member",
        )
        db.add(member)
        db.flush()
        project = verify_project_permission(db, testProject.id, other_user.id)
        assert project.id == testProject.id

    def test_viewer_member_fails(self, db, testProject):
        """viewer 角色层级 < member，不通过校验，但旧有属主校验兜底。"""
        other_user = User(
            username=f"viewer_{uuid.uuid4().hex[:8]}",
            email=f"viewer_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        db.add(other_user)
        db.flush()
        member = ProjectMember(
            project_id=testProject.id, user_id=other_user.id, role="viewer",
        )
        db.add(member)
        db.flush()
        # viewer 角色层级不足（< member），且非属主 → 403
        with pytest.raises(HTTPException) as exc_info:
            verify_project_permission(db, testProject.id, other_user.id)
        assert exc_info.value.status_code == 403


# ============================================================================
# verify_project_permission_async 测试
# ============================================================================


class TestVerifyProjectPermissionAsync:
    """verify_project_permission_async 异步版本测试。"""

    async def test_legacy_owner_passes(
        self, async_db, async_test_user, async_test_project
    ):
        """旧有属主校验通过（async）。"""
        project = await verify_project_permission_async(
            async_db, async_test_project.id, async_test_user.id,
        )
        assert project.id == async_test_project.id

    async def test_non_owner_fails(self, async_db, async_test_project):
        """非属主用户抛 403（async）。"""
        suffix = uuid.uuid4().hex[:8]
        other_user = User(
            username=f"noperm_async_{suffix}",
            email=f"noperm_async_{suffix}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        async_db.add(other_user)
        await async_db.flush()
        with pytest.raises(HTTPException) as exc_info:
            await verify_project_permission_async(
                async_db, async_test_project.id, other_user.id,
            )
        assert exc_info.value.status_code == 403

    async def test_project_member_passes(
        self, async_db, async_test_project
    ):
        """ProjectMember 成员通过校验（async）。"""
        suffix = uuid.uuid4().hex[:8]
        other_user = User(
            username=f"member_async_{suffix}",
            email=f"member_async_{suffix}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        async_db.add(other_user)
        await async_db.flush()
        member = ProjectMember(
            project_id=async_test_project.id, user_id=other_user.id, role="member",
        )
        async_db.add(member)
        await async_db.flush()
        project = await verify_project_permission_async(
            async_db, async_test_project.id, other_user.id,
        )
        assert project.id == async_test_project.id
