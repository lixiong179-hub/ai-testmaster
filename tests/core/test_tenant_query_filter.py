"""Phase 3 Task 9: 租户行级安全查询过滤器单元测试。

覆盖：
    - install/uninstall 生命周期
    - 查询过滤：tenant_id=1 只看到自己的数据
    - 跨租户隔离：tenant_id=1 看不到 tenant_id=2 的数据
    - 超级管理员绕过：tenant_id=None 看到全部数据
    - 自动填充：新建对象在 flush 时自动设置 tenant_id
    - 显式设置不覆盖：已设置 tenant_id 的对象不被覆盖
"""
import pytest

from app.core.tenant_context import (
    clear_current_tenant_id,
    set_current_tenant_id,
    tenant_scope,
)
from app.core.tenant_query_filter import (
    install_tenant_query_filter,
    is_tenant_filter_installed,
    uninstall_tenant_query_filter,
)


@pytest.fixture(autouse=True)
def tenant_filter_lifecycle():
    """每个测试自动安装/卸载过滤器，确保隔离。"""
    install_tenant_query_filter()
    yield
    uninstall_tenant_query_filter()
    clear_current_tenant_id()


@pytest.fixture
def tenants(db):
    """创建两个测试租户。"""
    from app.models import Tenant
    t1 = Tenant(name="Tenant A", slug="tenant-a", status="active")
    t2 = Tenant(name="Tenant B", slug="tenant-b", status="active")
    db.add(t1)
    db.add(t2)
    db.flush()
    return t1, t2


@pytest.fixture
def users_for_tenants(db, tenants):
    """为两个租户各创建一个用户。"""
    from app.models import User
    from app.utils.jwt_utils import get_password_hash
    t1, t2 = tenants
    u1 = User(
        username="user_a", email="a@test.com",
        password_hash=get_password_hash("pass"),
        tenant_id=t1.id,
    )
    u2 = User(
        username="user_b", email="b@test.com",
        password_hash=get_password_hash("pass"),
        tenant_id=t2.id,
    )
    db.add(u1)
    db.add(u2)
    db.flush()
    return u1, u2


@pytest.fixture
def projects_for_tenants(db, tenants, users_for_tenants):
    """为两个租户各创建一个项目。"""
    from app.models import Project
    t1, t2 = tenants
    u1, u2 = users_for_tenants
    p1 = Project(name="Project A", user_id=u1.id, tenant_id=t1.id, status=1)
    p2 = Project(name="Project B", user_id=u2.id, tenant_id=t2.id, status=1)
    db.add(p1)
    db.add(p2)
    db.flush()
    return p1, p2


class TestInstallLifecycle:
    """安装/卸载生命周期测试。"""

    def test_install_sets_flag(self) -> None:
        """安装后 is_installed 返回 True。"""
        assert is_tenant_filter_installed() is True

    def test_uninstall_clears_flag(self) -> None:
        """卸载后 is_installed 返回 False。"""
        uninstall_tenant_query_filter()
        assert is_tenant_filter_installed() is False
        # 重新安装供后续测试使用
        install_tenant_query_filter()

    def test_double_install_safe(self) -> None:
        """重复安装不报错。"""
        install_tenant_query_filter()
        install_tenant_query_filter()
        assert is_tenant_filter_installed() is True

    def test_double_uninstall_safe(self) -> None:
        """重复卸载不报错。"""
        uninstall_tenant_query_filter()
        uninstall_tenant_query_filter()
        assert is_tenant_filter_installed() is False
        install_tenant_query_filter()


class TestQueryFiltering:
    """查询过滤测试 — 核心行级安全场景。"""

    def test_tenant1_only_sees_own_projects(
        self, db, projects_for_tenants, tenants
    ) -> None:
        """租户 1 只能看到自己的项目。"""
        t1, t2 = tenants
        p1, p2 = projects_for_tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import Project
            projects = db.query(Project).all()
            tenant_ids = {p.tenant_id for p in projects}
            assert t1.id in tenant_ids
            assert t2.id not in tenant_ids

    def test_tenant2_only_sees_own_projects(
        self, db, projects_for_tenants, tenants
    ) -> None:
        """租户 2 只能看到自己的项目。"""
        t1, t2 = tenants
        with tenant_scope(tenant_id=t2.id):
            from app.models import Project
            projects = db.query(Project).all()
            for p in projects:
                assert p.tenant_id == t2.id

    def test_superadmin_sees_all(self, db, projects_for_tenants, tenants) -> None:
        """超级管理员（tenant_id=None）能看到全部项目。"""
        t1, t2 = tenants
        p1, p2 = projects_for_tenants
        # 不设置 tenant_scope = 系统级上下文
        from app.models import Project
        projects = db.query(Project).all()
        tenant_ids = {p.tenant_id for p in projects}
        assert t1.id in tenant_ids
        assert t2.id in tenant_ids

    def test_cross_tenant_access_denied(
        self, db, projects_for_tenants, tenants
    ) -> None:
        """跨租户访问被拒绝：按 ID 查询其他租户项目返回 None。"""
        t1, t2 = tenants
        p1, p2 = projects_for_tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import Project
            # 租户 1 查询租户 2 的项目
            leaked = db.query(Project).filter(Project.id == p2.id).first()
            assert leaked is None

    def test_user_isolation(self, db, users_for_tenants, tenants) -> None:
        """用户表也按租户隔离。"""
        t1, t2 = tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import User
            users = db.query(User).filter(User.is_superuser == False).all()
            for u in users:
                assert u.tenant_id == t1.id


class TestAutoPopulate:
    """before_flush 自动填充 tenant_id 测试。"""

    def test_new_project_gets_tenant_id(self, db, tenants, users_for_tenants) -> None:
        """新建项目在 flush 时自动填充 tenant_id。"""
        t1, t2 = tenants
        u1, _ = users_for_tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import Project
            proj = Project(name="Auto Populated", user_id=u1.id, status=1)
            db.add(proj)
            db.flush()
            assert proj.tenant_id == t1.id

    def test_explicit_tenant_id_not_overwritten(
        self, db, tenants, users_for_tenants
    ) -> None:
        """显式设置的 tenant_id 不被覆盖。"""
        t1, t2 = tenants
        u1, _ = users_for_tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import Project
            # 显式设置为另一个租户（模拟跨租户操作）
            proj = Project(
                name="Explicit Tenant", user_id=u1.id,
                status=1, tenant_id=t2.id,
            )
            db.add(proj)
            db.flush()
            # 显式设置的值保留
            assert proj.tenant_id == t2.id

    def test_no_populate_in_system_context(
        self, db, users_for_tenants
    ) -> None:
        """系统级上下文（tenant_id=None）不自动填充。"""
        u1, _ = users_for_tenants
        from app.models import Project
        proj = Project(name="No Tenant", user_id=u1.id, status=1)
        db.add(proj)
        db.flush()
        # 系统级上下文不填充
        assert proj.tenant_id is None

    def test_new_testcase_gets_tenant_id(
        self, db, tenants, projects_for_tenants
    ) -> None:
        """新建测试用例自动填充 tenant_id。"""
        t1, _ = tenants
        p1, _ = projects_for_tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import TestCase
            case = TestCase(
                case_no="TC-TEST-0001",
                project_id=p1.id,
                module="test",
                title="Test Case",
                precondition="none",
                steps_json=[],
                expected_result="pass",
                priority=1,
                case_type="API",
            )
            db.add(case)
            db.flush()
            assert case.tenant_id == t1.id


class TestNonTenantAwareModels:
    """非租户感知模型不受过滤影响。"""

    def test_tenant_model_not_filtered(self, db, tenants) -> None:
        """Tenant 模型本身不受 tenant_id 过滤。"""
        t1, t2 = tenants
        with tenant_scope(tenant_id=t1.id):
            from app.models import Tenant
            all_tenants = db.query(Tenant).all()
            # 应该看到所有租户（Tenant 不是 TenantAwareMixin）
            assert len(all_tenants) >= 2

    def test_role_not_filtered(self, db, tenants) -> None:
        """Role 模型不受 tenant_id 过滤。"""
        from app.models import Role
        role = Role(name="test_role_filter", permissions=[])
        db.add(role)
        db.flush()
        with tenant_scope(tenant_id=999):
            roles = db.query(Role).filter(Role.name == "test_role_filter").all()
            assert len(roles) == 1
