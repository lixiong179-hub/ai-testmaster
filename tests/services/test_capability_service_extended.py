import pytest
from app.services.test_capability_service import (
    create_capability,
    get_capability_by_id,
    get_capabilities_by_project,
    update_capability,
    delete_capability,
    DuplicateCapabilityKeyError,
    _UNSET,
)
from app.models.test_capability import TestCapability


class TestCreateCapability:
    def test_create_basic(self, db, testProject):
        cap = create_capability(db, testProject.id, "LOGIN", "登录功能")
        assert cap.id is not None
        assert cap.key == "LOGIN"
        assert cap.title == "登录功能"
        assert cap.status == "active"

    def test_create_with_description(self, db, testProject):
        cap = create_capability(
            db, testProject.id, "REG", "注册功能",
            description="用户注册流程", status="inactive",
        )
        assert cap.description == "用户注册流程"
        assert cap.status == "inactive"

    def test_duplicate_key_raises(self, db, testProject):
        create_capability(db, testProject.id, "DUP", "重复功能")
        with pytest.raises(DuplicateCapabilityKeyError):
            create_capability(db, testProject.id, "DUP", "重复功能2")


class TestGetCapabilityById:
    def test_get_existing(self, db, testProject):
        cap = create_capability(db, testProject.id, "GET", "查询功能")
        found = get_capability_by_id(db, cap.id)
        assert found is not None
        assert found.key == "GET"

    def test_get_nonexistent(self, db):
        result = get_capability_by_id(db, 99999)
        assert result is None


class TestGetCapabilitiesByProject:
    def test_filter_by_project(self, db, testProject):
        create_capability(db, testProject.id, "PROJ_A", "项目A功能")
        result = get_capabilities_by_project(db, testProject.id)
        assert len(result) >= 1

    def test_filter_by_status(self, db, testProject):
        create_capability(db, testProject.id, "ACTIVE", "活跃功能", status="active")
        create_capability(db, testProject.id, "INACTIVE", "非活跃功能", status="inactive")
        result = get_capabilities_by_project(db, testProject.id, status="active")
        assert all(c.status == "active" for c in result)

    def test_empty_project(self, db):
        result = get_capabilities_by_project(db, 99999)
        assert len(result) == 0


class TestUpdateCapability:
    def test_update_title(self, db, testProject):
        cap = create_capability(db, testProject.id, "UPD", "更新前")
        updated = update_capability(db, cap.id, title="更新后")
        assert updated.title == "更新后"

    def test_update_description_to_none(self, db, testProject):
        cap = create_capability(db, testProject.id, "CLR", "清除描述", description="有描述")
        updated = update_capability(db, cap.id, description=None)
        assert updated.description is None

    def test_update_nonexistent_returns_none(self, db):
        result = update_capability(db, 99999, title="不存在")
        assert result is None

    def test_update_key_conflict_raises(self, db, testProject):
        create_capability(db, testProject.id, "KEY1", "功能1")
        cap2 = create_capability(db, testProject.id, "KEY2", "功能2")
        with pytest.raises(DuplicateCapabilityKeyError):
            update_capability(db, cap2.id, key="KEY1")


class TestDeleteCapability:
    def test_delete_existing(self, db, testProject):
        cap = create_capability(db, testProject.id, "DEL", "删除功能")
        result = delete_capability(db, cap.id)
        assert result is True
        assert get_capability_by_id(db, cap.id) is None

    def test_delete_nonexistent(self, db):
        result = delete_capability(db, 99999)
        assert result is False
