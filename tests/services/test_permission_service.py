"""权限服务单元测试 - PermissionService, UserRoleService, RBACService"""
import pytest
from app.models.user import User, Role, Permission, user_role
from app.schemas.user import PermissionUpdate
from app.core.exception import BaseAPIException
from app.services.user_service.user_service import pwd_context
from app.services.permission_service import (
    PermissionService,
    UserRoleService,
    RBACService,
)


def _create_user(db, username="perm_user"):
    """Create user via ORM to avoid circular import through UserService."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        db.delete(existing)
        db.flush()
    user = User(
        username=username,
        email=f"{username}@test.com",
        password_hash=pwd_context.hash("Test@123"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _create_role(db, name="test_role", permissions=None):
    """Create role via ORM."""
    existing = db.query(Role).filter(Role.name == name).first()
    if existing:
        db.delete(existing)
        db.flush()
    role = Role(
        name=name,
        desc="test role",
        permissions=permissions or [],
    )
    db.add(role)
    db.flush()
    return role


def _create_permission(db, code="test:perm", name="测试权限"):
    # Ensure unique code AND name to avoid IntegrityError
    for field, val in [("code", code), ("name", name)]:
        existing = db.query(Permission).filter(getattr(Permission, field) == val).first()
        if existing:
            db.delete(existing)
            db.flush()
    return PermissionService.create_permission(db, {
        "name": name, "code": code, "type": "menu"
    })


class TestPermissionService:
    def test_create_permission(self, db):
        perm = _create_permission(db)
        assert perm.id is not None
        assert perm.code == "test:perm"

    def test_create_permission_dict_input(self, db):
        perm = PermissionService.create_permission(db, {
            "name": "字典权限", "code": "dict:perm", "type": "button"
        })
        assert perm.code == "dict:perm"

    def test_create_duplicate_code(self, db):
        # Create first permission directly (not via helper which would delete existing)
        PermissionService.create_permission(db, {
            "name": "重复测试权限", "code": "dup:code", "type": "menu"
        })
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.create_permission(db, {
                "name": "重复测试权限2", "code": "dup:code", "type": "menu"
            })
        assert exc_info.value.code == 400

    def test_get_permission_by_id(self, db):
        perm = _create_permission(db, code="get:perm")
        result = PermissionService.get_permission_by_id(db, perm.id)
        assert result is not None
        assert result.code == "get:perm"

    def test_get_permission_not_found(self, db):
        result = PermissionService.get_permission_by_id(db, 99999)
        assert result is None

    def test_update_permission(self, db):
        perm = _create_permission(db, code="upd:perm")
        result = PermissionService.update_permission(
            db, perm.id, PermissionUpdate(name="新名�?)
        )
        assert result.name == "新名�?

    def test_update_permission_dict(self, db):
        perm = _create_permission(db, code="upd2:perm")
        result = PermissionService.update_permission(
            db, perm.id, {"name": "字典更新"}
        )
        assert result.name == "字典更新"

    def test_update_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.update_permission(db, 99999, {"name": "x"})
        assert exc_info.value.code == 404

    def test_delete_permission(self, db):
        perm = _create_permission(db, code="del:perm")
        result = PermissionService.delete_permission(db, perm.id)
        assert result is True
        assert PermissionService.get_permission_by_id(db, perm.id) is None

    def test_delete_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.delete_permission(db, 99999)
        assert exc_info.value.code == 404

    def test_get_permissions_list(self, db):
        _create_permission(db, code="list1:perm", name="列表权限1")
        _create_permission(db, code="list2:perm", name="列表权限2")
        perms = PermissionService.get_permissions(db)
        assert len(perms) >= 2


class TestUserRoleService:
    def test_assign_role(self, db):
        user = _create_user(db, "assign_user")
        role = _create_role(db, "assign_role")
        result = UserRoleService.assign_role(db, user.id, role.id)
        assert result is True

    def test_assign_duplicate_role(self, db):
        user = _create_user(db, "dup_assign_user")
        role = _create_role(db, "dup_assign_role")
        UserRoleService.assign_role(db, user.id, role.id)
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, user.id, role.id)
        assert exc_info.value.code == 400

    def test_assign_nonexistent_user(self, db):
        role = _create_role(db, "no_user_role")
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, 99999, role.id)
        assert exc_info.value.code == 404

    def test_assign_nonexistent_role(self, db):
        user = _create_user(db, "no_role_user")
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, user.id, 99999)
        assert exc_info.value.code == 404

    def test_remove_role(self, db):
        user = _create_user(db, "remove_user")
        role = _create_role(db, "remove_role")
        UserRoleService.assign_role(db, user.id, role.id)
        result = UserRoleService.remove_role(db, user.id, role.id)
        assert result is True

    def test_remove_nonexistent_assignment(self, db):
        user = _create_user(db, "no_assign_user")
        role = _create_role(db, "no_assign_role")
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.remove_role(db, user.id, role.id)
        assert exc_info.value.code == 404

    def test_get_user_roles(self, db):
        user = _create_user(db, "roles_user")
        role1 = _create_role(db, "role_1")
        role2 = _create_role(db, "role_2")
        UserRoleService.assign_role(db, user.id, role1.id)
        UserRoleService.assign_role(db, user.id, role2.id)
        roles = UserRoleService.get_user_roles(db, user.id)
        assert len(roles) == 2

    def test_get_user_roles_empty(self, db):
        user = _create_user(db, "no_roles_user")
        roles = UserRoleService.get_user_roles(db, user.id)
        assert len(roles) == 0


class TestRBACService:
    def test_check_permission_granted(self, db):
        user = _create_user(db, "rbac_user")
        role = _create_role(db, "rbac_role", permissions=["user:create", "user:read"])
        UserRoleService.assign_role(db, user.id, role.id)
        assert RBACService.check_permission(db, user.id, "user:create") is True

    def test_check_permission_denied(self, db):
        user = _create_user(db, "rbac_deny_user")
        role = _create_role(db, "rbac_deny_role", permissions=["user:read"])
        UserRoleService.assign_role(db, user.id, role.id)
        assert RBACService.check_permission(db, user.id, "user:delete") is False

    def test_check_permission_no_roles(self, db):
        user = _create_user(db, "rbac_no_role_user")
        assert RBACService.check_permission(db, user.id, "any:perm") is False

    def test_check_permission_empty_permissions(self, db):
        user = _create_user(db, "rbac_empty_perm_user")
        role = _create_role(db, "rbac_empty_perm_role", permissions=[])
        UserRoleService.assign_role(db, user.id, role.id)
        assert RBACService.check_permission(db, user.id, "any:perm") is False

    def test_check_permission_multiple_roles(self, db):
        user = _create_user(db, "rbac_multi_user")
        role1 = _create_role(db, "multi_role1", permissions=["user:read"])
        role2 = _create_role(db, "multi_role2", permissions=["report:export"])
        UserRoleService.assign_role(db, user.id, role1.id)
        UserRoleService.assign_role(db, user.id, role2.id)
        assert RBACService.check_permission(db, user.id, "user:read") is True
        assert RBACService.check_permission(db, user.id, "report:export") is True
        assert RBACService.check_permission(db, user.id, "admin:all") is False
