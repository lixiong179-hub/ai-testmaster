"""Phase 3 Task 9: 租户上下文管理单元测试。

覆盖：
    - get/set/clear_current_tenant_id 基本功能
    - tenant_scope 上下文管理器（设置 + 恢复）
    - tenant_scope 嵌套场景
    - TenantAwareMixin 继承验证
"""
import pytest

from app.core.tenant_context import (
    TenantAwareMixin,
    clear_current_tenant_id,
    get_current_tenant_id,
    set_current_tenant_id,
    tenant_scope,
)


class TestTenantContext:
    """租户上下文 ContextVar 管理测试。"""

    def teardown_method(self) -> None:
        """每个测试后清除上下文，防止污染。"""
        clear_current_tenant_id()

    def test_default_is_none(self) -> None:
        """默认上下文为 None（系统级）。"""
        assert get_current_tenant_id() is None

    def test_set_and_get(self) -> None:
        """set 后 get 返回设置的值。"""
        set_current_tenant_id(42)
        assert get_current_tenant_id() == 42

    def test_clear(self) -> None:
        """clear 后恢复为 None。"""
        set_current_tenant_id(99)
        clear_current_tenant_id()
        assert get_current_tenant_id() is None

    def test_set_none_explicitly(self) -> None:
        """显式设置 None 表示超级管理员上下文。"""
        set_current_tenant_id(1)
        set_current_tenant_id(None)
        assert get_current_tenant_id() is None


class TestTenantScope:
    """tenant_scope 上下文管理器测试。"""

    def teardown_method(self) -> None:
        clear_current_tenant_id()

    def test_scope_sets_tenant(self) -> None:
        """进入 scope 后 tenant_id 生效。"""
        with tenant_scope(tenant_id=1):
            assert get_current_tenant_id() == 1

    def test_scope_restores_previous(self) -> None:
        """退出 scope 后恢复之前的值。"""
        set_current_tenant_id(5)
        with tenant_scope(tenant_id=10):
            assert get_current_tenant_id() == 10
        assert get_current_tenant_id() == 5

    def test_scope_restores_none(self) -> None:
        """退出 scope 后恢复 None（默认）。"""
        with tenant_scope(tenant_id=7):
            assert get_current_tenant_id() == 7
        assert get_current_tenant_id() is None

    def test_scope_with_none(self) -> None:
        """scope(None) 切换到系统级上下文。"""
        set_current_tenant_id(3)
        with tenant_scope(tenant_id=None):
            assert get_current_tenant_id() is None
        assert get_current_tenant_id() == 3

    def test_nested_scopes(self) -> None:
        """嵌套 scope 正确恢复每一层。"""
        set_current_tenant_id(1)
        with tenant_scope(tenant_id=2):
            assert get_current_tenant_id() == 2
            with tenant_scope(tenant_id=3):
                assert get_current_tenant_id() == 3
            assert get_current_tenant_id() == 2
        assert get_current_tenant_id() == 1

    def test_scope_restores_on_exception(self) -> None:
        """scope 内抛异常时仍正确恢复。"""
        set_current_tenant_id(1)
        with pytest.raises(RuntimeError, match="boom"):
            with tenant_scope(tenant_id=2):
                raise RuntimeError("boom")
        assert get_current_tenant_id() == 1


class TestTenantAwareMixin:
    """TenantAwareMixin 继承验证。"""

    def test_all_core_models_inherit_mixin(self) -> None:
        """所有核心业务模型应继承 TenantAwareMixin。"""
        from app.models import (
            Iteration,
            Project,
            ProjectFile,
            Requirement,
            TestCase,
            TestCapability,
            TestPoint,
            TestReport,
            TestResult,
            TestTask,
            User,
        )

        tenant_aware_models = [
            User, Project, ProjectFile,
            TestCase, TestTask, TestResult, TestReport,
            Iteration, TestPoint, TestCapability, Requirement,
        ]
        for model in tenant_aware_models:
            assert issubclass(model, TenantAwareMixin), (
                f"{model.__name__} 应继承 TenantAwareMixin"
            )

    def test_tenant_model_not_aware(self) -> None:
        """Tenant 模型本身不应继承 TenantAwareMixin（无 tenant_id 列）。"""
        from app.models import Tenant
        assert not issubclass(Tenant, TenantAwareMixin)

    def test_role_not_aware(self) -> None:
        """Role 模型是全局的，不应继承 TenantAwareMixin。"""
        from app.models import Role
        assert not issubclass(Role, TenantAwareMixin)
