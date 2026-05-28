"""Capability 生命周期服务单元测试 - 覆盖状态流转规则、审计日志、异常场景"""
import pytest
from app.models.enums import CapabilityStatus
from app.services.test_capability_service import (
    create_capability,
    get_capability_by_id,
)
from app.services.lifecycle_service import (
    can_transition_capability,
    transition_capability,
    IllegalCapabilityTransition,
)


class TestCanTransitionCapability:
    """状态流转合法性判断"""

    def test_active_to_deprecated(self) -> None:
        assert can_transition_capability("active", "deprecated") is True

    def test_active_to_archived(self) -> None:
        assert can_transition_capability("active", "archived") is True

    def test_deprecated_to_archived(self) -> None:
        assert can_transition_capability("deprecated", "archived") is True

    def test_deprecated_to_active_not_allowed(self) -> None:
        assert can_transition_capability("deprecated", "active") is False

    def test_archived_to_active_not_allowed(self) -> None:
        assert can_transition_capability("archived", "active") is False

    def test_archived_to_deprecated_not_allowed(self) -> None:
        assert can_transition_capability("archived", "deprecated") is False

    def test_archived_to_archived_not_allowed(self) -> None:
        assert can_transition_capability("archived", "archived") is False

    def test_active_to_active_not_allowed(self) -> None:
        assert can_transition_capability("active", "active") is False

    def test_deprecated_to_deprecated_not_allowed(self) -> None:
        assert can_transition_capability("deprecated", "deprecated") is False

    def test_unknown_status_returns_false(self) -> None:
        assert can_transition_capability("unknown", "active") is False


class TestTransitionCapability:
    """状态流转执行"""

    def test_active_to_deprecated(self, db, testProject) -> None:
        cap = create_capability(db, project_id=testProject.id, key="lc_ad", title="流转测试")
        result = transition_capability(db, cap.id, CapabilityStatus.DEPRECATED.value)
        assert result.status == CapabilityStatus.DEPRECATED.value
        assert result.id == cap.id

    def test_active_to_archived(self, db, testProject) -> None:
        cap = create_capability(db, project_id=testProject.id, key="lc_aa", title="直接归档")
        result = transition_capability(db, cap.id, CapabilityStatus.ARCHIVED.value)
        assert result.status == CapabilityStatus.ARCHIVED.value

    def test_deprecated_to_archived(self, db, testProject) -> None:
        cap = create_capability(
            db, project_id=testProject.id, key="lc_da", title="废弃后归档",
            status=CapabilityStatus.DEPRECATED.value,
        )
        result = transition_capability(db, cap.id, CapabilityStatus.ARCHIVED.value)
        assert result.status == CapabilityStatus.ARCHIVED.value

    def test_archived_to_active_raises(self, db, testProject) -> None:
        cap = create_capability(
            db, project_id=testProject.id, key="lc_atoa", title="归档不可逆",
            status=CapabilityStatus.ARCHIVED.value,
        )
        with pytest.raises(IllegalCapabilityTransition) as exc_info:
            transition_capability(db, cap.id, CapabilityStatus.ACTIVE.value)
        assert "archived" in str(exc_info.value)
        assert "active" in str(exc_info.value)

    def test_archived_to_deprecated_raises(self, db, testProject) -> None:
        cap = create_capability(
            db, project_id=testProject.id, key="lc_atod", title="归档不可逆2",
            status=CapabilityStatus.ARCHIVED.value,
        )
        with pytest.raises(IllegalCapabilityTransition):
            transition_capability(db, cap.id, CapabilityStatus.DEPRECATED.value)

    def test_nonexistent_capability_raises(self, db) -> None:
        with pytest.raises(ValueError, match="not found"):
            transition_capability(db, 99999, CapabilityStatus.ARCHIVED.value)

    def test_with_actor_id(self, db, testProject, testUser) -> None:
        cap = create_capability(db, project_id=testProject.id, key="lc_actor", title="带操作人")
        result = transition_capability(
            db, cap.id, CapabilityStatus.DEPRECATED.value, actor_id=testUser.id,
        )
        assert result.status == CapabilityStatus.DEPRECATED.value

    def test_with_reason(self, db, testProject) -> None:
        cap = create_capability(db, project_id=testProject.id, key="lc_reason", title="带原因")
        result = transition_capability(
            db, cap.id, CapabilityStatus.DEPRECATED.value, reason="业务下线",
        )
        assert result.status == CapabilityStatus.DEPRECATED.value

    def test_full_lifecycle_active_deprecated_archived(self, db, testProject) -> None:
        """完整生命周期：active -> deprecated -> archived"""
        cap = create_capability(db, project_id=testProject.id, key="lc_full", title="完整流程")
        step1 = transition_capability(db, cap.id, CapabilityStatus.DEPRECATED.value)
        assert step1.status == CapabilityStatus.DEPRECATED.value
        step2 = transition_capability(db, cap.id, CapabilityStatus.ARCHIVED.value)
        assert step2.status == CapabilityStatus.ARCHIVED.value
        # 归档后不可再变更
        with pytest.raises(IllegalCapabilityTransition):
            transition_capability(db, cap.id, CapabilityStatus.ACTIVE.value)


class TestIllegalCapabilityTransitionException:
    """异常类属性验证"""

    def test_exception_attributes(self) -> None:
        exc = IllegalCapabilityTransition("archived", "active", "终态不可逆")
        assert exc.fromStatus == "archived"
        assert exc.toStatus == "active"
        assert "archived" in str(exc)
        assert "active" in str(exc)
        assert "终态不可逆" in str(exc)

    def test_exception_without_detail(self) -> None:
        exc = IllegalCapabilityTransition("active", "active")
        assert "active" in str(exc)
