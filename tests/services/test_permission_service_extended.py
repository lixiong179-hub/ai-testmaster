import pytest
from app.services.permission_service import (
    PermissionService,
    UserRoleService,
    RBACService,
)
from app.schemas.user import PermissionCreate, PermissionUpdate
from app.models.user import Permission, Role, user_role
from app.core.exception import BaseAPIException


class TestPermissionService:
    def test_create_permission(self, db):
        perm_in = PermissionCreate(name="测试权限", code="test:perm", type="menu")
        perm = PermissionService.create_permission(db, perm_in)
        assert perm.id is not None
        assert perm.code == "test:perm"

    def test_create_permission_from_dict(self, db):
        perm = PermissionService.create_permission(
            db, {"name": "字典权限", "code": "dict:perm", "type": "menu"}
        )
        assert perm.code == "dict:perm"

    def test_create_duplicate_code_raises(self, db):
        perm_in = PermissionCreate(name="重复权限", code="dup:perm", type="menu")
        PermissionService.create_permission(db, perm_in)
        with pytest.raises(BaseAPIException, match="权限编码已存在"):
            PermissionService.create_permission(db, perm_in)

    def test_get_permission_by_id(self, db):
        perm_in = PermissionCreate(name="查询权限", code="get:perm", type="menu")
        created = PermissionService.create_permission(db, perm_in)
        found = PermissionService.get_permission_by_id(db, created.id)
        assert found is not None
        assert found.code == "get:perm"

    def test_get_permission_not_found(self, db):
        result = PermissionService.get_permission_by_id(db, 99999)
        assert result is None

    def test_update_permission(self, db):
        perm_in = PermissionCreate(name="更新前", code="upd:perm", type="menu")
        created = PermissionService.create_permission(db, perm_in)
        updated = PermissionService.update_permission(
            db, created.id, PermissionUpdate(name="更新后")
        )
        assert updated.name == "更新后"

    def test_update_permission_from_dict(self, db):
        perm_in = PermissionCreate(name="字典更新前", code="upddict:perm", type="menu")
        created = PermissionService.create_permission(db, perm_in)
        updated = PermissionService.update_permission(
            db, created.id, {"name": "字典更新后"}
        )
        assert updated.name == "字典更新后"

    def test_update_nonexistent_raises(self, db):
        with pytest.raises(BaseAPIException, match="权限不存在"):
            PermissionService.update_permission(db, 99999, {"name": "x"})

    def test_delete_permission(self, db):
        perm_in = PermissionCreate(name="删除权限", code="del:perm", type="menu")
        created = PermissionService.create_permission(db, perm_in)
        result = PermissionService.delete_permission(db, created.id)
        assert result is True
        assert PermissionService.get_permission_by_id(db, created.id) is None

    def test_delete_nonexistent_raises(self, db):
        with pytest.raises(BaseAPIException, match="权限不存在"):
            PermissionService.delete_permission(db, 99999)

    def test_get_permissions(self, db):
        result = PermissionService.get_permissions(db, skip=0, limit=10)
        assert isinstance(result, list)


class TestUserRoleService:
    def test_assign_role(self, db, testUser):
        role = Role(name="test_role_assign", permissions=["test:perm"])
        db.add(role)
        db.flush()
        result = UserRoleService.assign_role(db, testUser.id, role.id)
        assert result is True

    def test_assign_duplicate_role_raises(self, db, testUser):
        role = Role(name="test_role_dup", permissions=["test:perm"])
        db.add(role)
        db.flush()
        UserRoleService.assign_role(db, testUser.id, role.id)
        with pytest.raises(BaseAPIException, match="角色已分配"):
            UserRoleService.assign_role(db, testUser.id, role.id)

    def test_assign_nonexistent_user_raises(self, db):
        with pytest.raises(BaseAPIException, match="用户不存在"):
            UserRoleService.assign_role(db, 99999, 1)

    def test_assign_nonexistent_role_raises(self, db, testUser):
        with pytest.raises(BaseAPIException, match="角色不存在"):
            UserRoleService.assign_role(db, testUser.id, 99999)

    def test_remove_role(self, db, testUser):
        role = Role(name="test_role_remove", permissions=["test:perm"])
        db.add(role)
        db.flush()
        UserRoleService.assign_role(db, testUser.id, role.id)
        result = UserRoleService.remove_role(db, testUser.id, role.id)
        assert result is True

    def test_remove_nonexistent_raises(self, db, testUser):
        with pytest.raises(BaseAPIException, match="角色分配不存在"):
            UserRoleService.remove_role(db, testUser.id, 99999)

    def test_get_user_roles(self, db, testUser):
        role = Role(name="test_role_get", permissions=["test:perm"])
        db.add(role)
        db.flush()
        UserRoleService.assign_role(db, testUser.id, role.id)
        roles = UserRoleService.get_user_roles(db, testUser.id)
        assert len(roles) >= 1


class TestRBACService:
    def test_check_permission_has(self, db, testUser):
        role = Role(name="rbac_role_has", permissions=["rbac:test"])
        db.add(role)
        db.flush()
        UserRoleService.assign_role(db, testUser.id, role.id)
        assert RBACService.check_permission(db, testUser.id, "rbac:test") is True

    def test_check_permission_no_role(self, db, testUser):
        assert RBACService.check_permission(db, testUser.id, "nonexistent:perm") is False

    def test_check_permission_role_without_perm(self, db, testUser):
        role = Role(name="rbac_role_empty", permissions=[])
        db.add(role)
        db.flush()
        UserRoleService.assign_role(db, testUser.id, role.id)
        assert RBACService.check_permission(db, testUser.id, "missing:perm") is False
