"""角色服务单元测试 - RoleService"""
import pytest
from app.models.user import Role
from app.schemas.user import RoleCreate, RoleUpdate
from app.core.exception import BaseAPIException
from app.services.role_service.role_service import RoleService


def _create_role(db, name="svc_role", permissions=None):
    """Helper to create role via RoleService."""
    return RoleService.create_role(db, RoleCreate(
        name=name, desc="test", permissions=permissions or [],
    ))


class TestCreateRole:
    def test_create_with_schema(self, db):
        role = _create_role(db, "create_role")
        assert role.id is not None
        assert role.name == "create_role"

    def test_create_with_dict(self, db):
        role = RoleService.create_role(db, {
            "name": "dict_role", "desc": "dict desc", "permissions": ["read"],
        })
        assert role.name == "dict_role"
        assert role.permissions == ["read"]

    def test_create_duplicate_name(self, db):
        _create_role(db, "dup_role")
        with pytest.raises(BaseAPIException) as exc_info:
            _create_role(db, "dup_role")
        assert exc_info.value.code == 400


class TestGetRoleById:
    def test_found(self, db):
        role = _create_role(db, "getbyid_role")
        result = RoleService.get_role_by_id(db, role.id)
        assert result is not None
        assert result.name == "getbyid_role"

    def test_not_found(self, db):
        result = RoleService.get_role_by_id(db, 99999)
        assert result is None


class TestUpdateRole:
    def test_update_with_schema(self, db):
        role = _create_role(db, "upd_schema_role")
        result = RoleService.update_role(db, role.id, RoleUpdate(desc="new desc"))
        assert result.desc == "new desc"

    def test_update_with_dict(self, db):
        role = _create_role(db, "upd_dict_role")
        result = RoleService.update_role(db, role.id, {"permissions": ["admin:all"]})
        assert result.permissions == ["admin:all"]

    def test_update_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            RoleService.update_role(db, 99999, {"desc": "x"})
        assert exc_info.value.code == 404


class TestDeleteRole:
    def test_delete_success(self, db):
        role = _create_role(db, "del_role")
        result = RoleService.delete_role(db, role.id)
        assert result is True
        assert RoleService.get_role_by_id(db, role.id) is None

    def test_delete_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            RoleService.delete_role(db, 99999)
        assert exc_info.value.code == 404


class TestGetRoles:
    def test_get_roles(self, db):
        _create_role(db, "list_role")
        roles = RoleService.get_roles(db)
        assert len(roles) >= 1

    def test_get_roles_pagination(self, db):
        roles = RoleService.get_roles(db, skip=0, limit=1)
        assert len(roles) <= 1
