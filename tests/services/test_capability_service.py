"""TestCapability 服务单元测试 - 覆盖创建、查询、列表、状态过滤、唯一约束、软删除"""
import pytest
from app.models.test_capability import TestCapability
from app.models.enums import CapabilityStatus
from app.services.test_capability_service import (
    create_capability,
    get_capability_by_id,
    get_capabilities_by_project,
    update_capability,
    delete_capability,
    DuplicateCapabilityKeyError,
)


class TestCreateCapability:
    """创建能力"""

    def test_create_success(self, db, testProject):
        cap = create_capability(db, project_id=testProject.id, key="user_mgmt", title="用户管理")
        assert cap.id is not None
        assert cap.key == "user_mgmt"
        assert cap.title == "用户管理"
        assert cap.status == "active"
        assert cap.project_id == testProject.id

    def test_create_with_description(self, db, testProject):
        cap = create_capability(
            db, project_id=testProject.id, key="order", title="订单处理",
            description="订单相关业务能力"
        )
        assert cap.description == "订单相关业务能力"

    def test_create_with_status(self, db, testProject):
        cap = create_capability(
            db, project_id=testProject.id, key="legacy", title="遗留模块",
            status="deprecated"
        )
        assert cap.status == "deprecated"

    def test_create_duplicate_key_same_project_raises(self, db, testProject):
        create_capability(db, project_id=testProject.id, key="dup_key", title="第一个")
        with pytest.raises(DuplicateCapabilityKeyError):
            create_capability(db, project_id=testProject.id, key="dup_key", title="第二个")

    def test_create_same_key_different_project_ok(self, db, testProject):
        from app.models.project import Project
        from app.models.user import User
        from app.services.user_service.user_service import pwd_context

        user2 = User(
            username="cap_test_user2",
            email="cap2@test.com",
            password_hash=pwd_context.hash("Test@123"),
            is_active=True,
        )
        db.add(user2)
        db.flush()
        proj2 = Project(name="proj2_for_cap", user_id=user2.id, status=1, project_type="web")
        db.add(proj2)
        db.flush()

        create_capability(db, project_id=testProject.id, key="shared_key", title="项目1的能力")
        cap2 = create_capability(db, project_id=proj2.id, key="shared_key", title="项目2的能力")
        assert cap2.project_id == proj2.id


class TestGetCapability:
    """查询能力"""

    def test_get_by_id(self, db, testProject):
        cap = create_capability(db, project_id=testProject.id, key="query_test", title="查询测试")
        found = get_capability_by_id(db, cap.id)
        assert found is not None
        assert found.key == "query_test"

    def test_get_nonexistent_returns_none(self, db):
        assert get_capability_by_id(db, 99999) is None


class TestListCapabilities:
    """按项目列出能力"""

    def test_list_by_project(self, db, testProject):
        create_capability(db, project_id=testProject.id, key="list_a", title="A")
        create_capability(db, project_id=testProject.id, key="list_b", title="B")
        caps = get_capabilities_by_project(db, project_id=testProject.id)
        keys = {c.key for c in caps}
        assert "list_a" in keys
        assert "list_b" in keys

    def test_list_filter_by_status(self, db, testProject):
        create_capability(db, project_id=testProject.id, key="active_one", title="活跃", status="active")
        create_capability(db, project_id=testProject.id, key="depr_one", title="废弃", status="deprecated")
        active_caps = get_capabilities_by_project(db, project_id=testProject.id, status="active")
        assert all(c.status == "active" for c in active_caps)
        depr_caps = get_capabilities_by_project(db, project_id=testProject.id, status="deprecated")
        assert all(c.status == "deprecated" for c in depr_caps)

    def test_list_default_excludes_archived(self, db, testProject):
        """默认查询不包含已归档能力"""
        create_capability(db, project_id=testProject.id, key="active_cap", title="活跃", status="active")
        create_capability(db, project_id=testProject.id, key="archived_cap", title="已归档", status="archived")
        caps = get_capabilities_by_project(db, project_id=testProject.id)
        keys = {c.key for c in caps}
        assert "active_cap" in keys
        assert "archived_cap" not in keys

    def test_list_include_archived(self, db, testProject):
        """include_archived=True 时包含已归档能力"""
        create_capability(db, project_id=testProject.id, key="active_cap2", title="活跃", status="active")
        create_capability(db, project_id=testProject.id, key="archived_cap2", title="已归档", status="archived")
        caps = get_capabilities_by_project(db, project_id=testProject.id, include_archived=True)
        keys = {c.key for c in caps}
        assert "active_cap2" in keys
        assert "archived_cap2" in keys

    def test_list_empty_for_new_project(self, db, testProject):
        caps = get_capabilities_by_project(db, project_id=testProject.id)
        for c in caps:
            assert c.project_id == testProject.id


class TestUpdateCapability:
    """更新能力"""

    def test_update_title(self, db, testProject):
        cap = create_capability(db, project_id=testProject.id, key="upd_test", title="旧标题")
        updated = update_capability(db, cap.id, title="新标题")
        assert updated.title == "新标题"

    def test_update_key_duplicate_raises(self, db, testProject):
        create_capability(db, project_id=testProject.id, key="existing_key", title="已存在")
        cap2 = create_capability(db, project_id=testProject.id, key="to_update", title="待更新")
        with pytest.raises(DuplicateCapabilityKeyError):
            update_capability(db, cap2.id, key="existing_key")

    def test_update_nonexistent_returns_none(self, db):
        result = update_capability(db, 99999, title="不存在")
        assert result is None


class TestDeleteCapability:
    """软删除能力（status 置为 archived）"""

    def test_delete_success(self, db, testProject):
        cap = create_capability(db, project_id=testProject.id, key="del_test", title="待删除")
        result = delete_capability(db, cap.id)
        assert result is not None
        assert result.status == CapabilityStatus.ARCHIVED.value
        # 记录仍存在，status 为 archived
        found = get_capability_by_id(db, cap.id)
        assert found is not None
        assert found.status == CapabilityStatus.ARCHIVED.value

    def test_delete_with_actor_id(self, db, testProject, testUser):
        cap = create_capability(db, project_id=testProject.id, key="del_actor", title="带操作人删除")
        result = delete_capability(db, cap.id, actor_id=testUser.id)
        assert result is not None
        assert result.status == CapabilityStatus.ARCHIVED.value

    def test_delete_nonexistent_returns_none(self, db):
        result = delete_capability(db, 99999)
        assert result is None

    def test_delete_archived_capability_idempotent(self, db, testProject):
        """已归档能力再次删除应幂等返回该能力，不抛异常"""
        cap = create_capability(
            db, project_id=testProject.id, key="del_archived", title="已归档",
            status=CapabilityStatus.ARCHIVED.value,
        )
        result = delete_capability(db, cap.id)
        assert result is not None
        assert result.status == CapabilityStatus.ARCHIVED.value
