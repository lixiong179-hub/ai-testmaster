import uuid
import pytest
from app.services.user_role_service import UserService, RoleService, pwd_context
from app.services.permission_service import PermissionService, UserRoleService, RBACService
from app.schemas.user import UserCreate, UserUpdate, RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate
from app.core.exception import BaseAPIException
from app.models.user import User, Role, Permission, user_role
from tests.helpers import createTestUser, createTestProject


class TestUserServiceCreate:
    def test_create_user_normal(self, db):
        userCreate = UserCreate(
            username=f"svc_user_{uuid.uuid4().hex[:8]}",
            email=f"svc_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        assert user is not None
        assert user.id is not None
        assert user.username == userCreate.username
        assert user.email == userCreate.email
        assert user.password_hash != "Test@123456"

    def test_create_user_with_dict(self, db):
        userData = {
            "username": f"svc_dict_{uuid.uuid4().hex[:8]}",
            "email": f"svc_dict_{uuid.uuid4().hex[:8]}@test.com",
            "password": "Test@123456",
        }
        user = UserService.create_user(db, userData)
        assert user is not None
        assert user.username == userData["username"]

    def test_create_user_duplicate_username(self, db):
        username = f"svc_dup_{uuid.uuid4().hex[:8]}"
        userCreate1 = UserCreate(
            username=username,
            email=f"svc_dup1_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        UserService.create_user(db, userCreate1)
        userCreate2 = UserCreate(
            username=username,
            email=f"svc_dup2_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.create_user(db, userCreate2)
        assert "用户名已存在" in exc_info.value.msg

    def test_create_user_duplicate_email(self, db):
        email = f"svc_dupemail_{uuid.uuid4().hex[:8]}@test.com"
        userCreate1 = UserCreate(
            username=f"svc_email1_{uuid.uuid4().hex[:8]}",
            email=email,
            password="Test@123456",
        )
        UserService.create_user(db, userCreate1)
        userCreate2 = UserCreate(
            username=f"svc_email2_{uuid.uuid4().hex[:8]}",
            email=email,
            password="Test@123456",
        )
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.create_user(db, userCreate2)
        assert "邮箱已存在" in exc_info.value.msg

    def test_create_user_with_phone(self, db):
        userCreate = UserCreate(
            username=f"svc_phone_{uuid.uuid4().hex[:8]}",
            email=f"svc_phone_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
            phone="13800138000",
        )
        user = UserService.create_user(db, userCreate)
        assert user.phone == "13800138000"


class TestUserServiceAuthenticate:
    def test_authenticate_user_success(self, db):
        username = f"svc_auth_{uuid.uuid4().hex[:8]}"
        password = "Test@123456"
        userCreate = UserCreate(
            username=username,
            email=f"svc_auth_{uuid.uuid4().hex[:8]}@test.com",
            password=password,
        )
        UserService.create_user(db, userCreate)
        result = UserService.authenticate_user(db, username, password)
        assert result is not None
        assert result.username == username

    def test_authenticate_user_wrong_password(self, db):
        username = f"svc_wrongpw_{uuid.uuid4().hex[:8]}"
        userCreate = UserCreate(
            username=username,
            email=f"svc_wrongpw_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        UserService.create_user(db, userCreate)
        result = UserService.authenticate_user(db, username, "WrongPassword1")
        assert result is None

    def test_authenticate_user_nonexistent(self, db):
        result = UserService.authenticate_user(db, "nonexistent_user_xyz", "password")
        assert result is None

    def test_authenticate_user_inactive(self, db):
        username = f"svc_inactive_{uuid.uuid4().hex[:8]}"
        userCreate = UserCreate(
            username=username,
            email=f"svc_inactive_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        user.is_active = False
        db.commit()
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.authenticate_user(db, username, "Test@123456")
        assert "禁用" in exc_info.value.msg


class TestUserServiceGet:
    def test_get_user_by_id(self, db):
        userCreate = UserCreate(
            username=f"svc_getid_{uuid.uuid4().hex[:8]}",
            email=f"svc_getid_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        found = UserService.get_user_by_id(db, user.id)
        assert found is not None
        assert found.id == user.id

    def test_get_user_by_id_nonexistent(self, db):
        found = UserService.get_user_by_id(db, 99999)
        assert found is None

    def test_get_user_by_username(self, db):
        username = f"svc_getname_{uuid.uuid4().hex[:8]}"
        userCreate = UserCreate(
            username=username,
            email=f"svc_getname_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        UserService.create_user(db, userCreate)
        found = UserService.get_user_by_username(db, username)
        assert found is not None
        assert found.username == username

    def test_get_user_by_username_nonexistent(self, db):
        found = UserService.get_user_by_username(db, "nonexistent_username_xyz")
        assert found is None

    def test_get_users(self, db):
        users = UserService.get_users(db, skip=0, limit=10)
        assert isinstance(users, list)

    def test_get_users_pagination(self, db):
        first = UserService.get_users(db, skip=0, limit=1)
        assert len(first) <= 1


class TestUserServiceUpdate:
    def test_update_user_normal(self, db):
        userCreate = UserCreate(
            username=f"svc_upd_{uuid.uuid4().hex[:8]}",
            email=f"svc_upd_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        userUpdate = UserUpdate(email=f"updated_{uuid.uuid4().hex[:8]}@test.com")
        updated = UserService.update_user(db, user.id, userUpdate)
        assert updated.email != userCreate.email

    def test_update_user_with_dict(self, db):
        userCreate = UserCreate(
            username=f"svc_upddict_{uuid.uuid4().hex[:8]}",
            email=f"svc_upddict_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        updated = UserService.update_user(db, user.id, {"phone": "13900139000"})
        assert updated.phone == "13900139000"

    def test_update_user_nonexistent(self, db):
        userUpdate = UserUpdate(email="no@exist.com")
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.update_user(db, 99999, userUpdate)
        assert "不存在" in exc_info.value.msg


class TestUserServiceDelete:
    def test_delete_user_normal(self, db):
        userCreate = UserCreate(
            username=f"svc_del_{uuid.uuid4().hex[:8]}",
            email=f"svc_del_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        result = UserService.delete_user(db, user.id)
        assert result is True
        found = UserService.get_user_by_id(db, user.id)
        assert found is None

    def test_delete_user_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.delete_user(db, 99999)
        assert "不存在" in exc_info.value.msg


class TestUserServicePassword:
    def test_verify_password_correct(self):
        hashed = pwd_context.hash("Test@123456")
        assert pwd_context.verify("Test@123456", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = pwd_context.hash("Test@123456")
        assert pwd_context.verify("WrongPassword", hashed) is False

    def test_get_password_hash(self):
        hashed = UserService.get_password_hash("Test@123456")
        assert hashed != "Test@123456"
        assert UserService.verify_password("Test@123456", hashed) is True

    def test_password_hash_different_each_time(self):
        hash1 = UserService.get_password_hash("Test@123456")
        hash2 = UserService.get_password_hash("Test@123456")
        assert hash1 != hash2


class TestRoleService:
    def test_create_role_normal(self, db):
        roleCreate = RoleCreate(
            name=f"svc_role_{uuid.uuid4().hex[:8]}",
            desc="test role",
            permissions=["read", "write"],
        )
        role = RoleService.create_role(db, roleCreate)
        assert role is not None
        assert role.id is not None
        assert role.name == roleCreate.name
        assert role.permissions == ["read", "write"]

    def test_create_role_with_dict(self, db):
        roleData = {
            "name": f"svc_roledict_{uuid.uuid4().hex[:8]}",
            "desc": "dict role",
        }
        role = RoleService.create_role(db, roleData)
        assert role is not None

    def test_create_role_duplicate_name(self, db):
        name = f"svc_duprole_{uuid.uuid4().hex[:8]}"
        roleCreate1 = RoleCreate(name=name, desc="first")
        RoleService.create_role(db, roleCreate1)
        roleCreate2 = RoleCreate(name=name, desc="second")
        with pytest.raises(BaseAPIException) as exc_info:
            RoleService.create_role(db, roleCreate2)
        assert "已存在" in exc_info.value.msg

    def test_get_role_by_id(self, db):
        roleCreate = RoleCreate(
            name=f"svc_getrole_{uuid.uuid4().hex[:8]}",
            desc="get role",
        )
        role = RoleService.create_role(db, roleCreate)
        found = RoleService.get_role_by_id(db, role.id)
        assert found is not None
        assert found.id == role.id

    def test_get_role_by_id_nonexistent(self, db):
        found = RoleService.get_role_by_id(db, 99999)
        assert found is None

    def test_update_role_normal(self, db):
        roleCreate = RoleCreate(
            name=f"svc_updrole_{uuid.uuid4().hex[:8]}",
            desc="original",
        )
        role = RoleService.create_role(db, roleCreate)
        roleUpdate = RoleUpdate(desc="updated")
        updated = RoleService.update_role(db, role.id, roleUpdate)
        assert updated.desc == "updated"

    def test_update_role_nonexistent(self, db):
        roleUpdate = RoleUpdate(desc="should not update")
        with pytest.raises(BaseAPIException) as exc_info:
            RoleService.update_role(db, 99999, roleUpdate)
        assert "不存在" in exc_info.value.msg

    def test_delete_role_normal(self, db):
        roleCreate = RoleCreate(
            name=f"svc_delrole_{uuid.uuid4().hex[:8]}",
            desc="to delete",
        )
        role = RoleService.create_role(db, roleCreate)
        result = RoleService.delete_role(db, role.id)
        assert result is True
        found = RoleService.get_role_by_id(db, role.id)
        assert found is None

    def test_delete_role_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            RoleService.delete_role(db, 99999)
        assert "不存在" in exc_info.value.msg

    def test_get_roles(self, db):
        roles = RoleService.get_roles(db, skip=0, limit=10)
        assert isinstance(roles, list)


class TestPermissionService:
    def test_create_permission_normal(self, db):
        permCreate = PermissionCreate(
            name=f"svc_perm_{uuid.uuid4().hex[:8]}",
            code=f"svc_perm_code_{uuid.uuid4().hex[:8]}",
            type="api",
        )
        perm = PermissionService.create_permission(db, permCreate)
        assert perm is not None
        assert perm.id is not None
        assert perm.code == permCreate.code

    def test_create_permission_with_dict(self, db):
        permData = {
            "name": f"svc_permdict_{uuid.uuid4().hex[:8]}",
            "code": f"svc_permdict_code_{uuid.uuid4().hex[:8]}",
            "type": "menu",
        }
        perm = PermissionService.create_permission(db, permData)
        assert perm is not None

    def test_create_permission_duplicate_code(self, db):
        code = f"svc_dupperm_{uuid.uuid4().hex[:8]}"
        permCreate1 = PermissionCreate(name="perm1", code=code, type="api")
        PermissionService.create_permission(db, permCreate1)
        permCreate2 = PermissionCreate(name="perm2", code=code, type="api")
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.create_permission(db, permCreate2)
        assert "已存在" in exc_info.value.msg

    def test_get_permission_by_id(self, db):
        permCreate = PermissionCreate(
            name=f"svc_getperm_{uuid.uuid4().hex[:8]}",
            code=f"svc_getperm_code_{uuid.uuid4().hex[:8]}",
            type="button",
        )
        perm = PermissionService.create_permission(db, permCreate)
        found = PermissionService.get_permission_by_id(db, perm.id)
        assert found is not None
        assert found.id == perm.id

    def test_get_permission_by_id_nonexistent(self, db):
        found = PermissionService.get_permission_by_id(db, 99999)
        assert found is None

    def test_update_permission_normal(self, db):
        permCreate = PermissionCreate(
            name=f"svc_updperm_{uuid.uuid4().hex[:8]}",
            code=f"svc_updperm_code_{uuid.uuid4().hex[:8]}",
            type="api",
        )
        perm = PermissionService.create_permission(db, permCreate)
        permUpdate = PermissionUpdate(name="updated_perm_name")
        updated = PermissionService.update_permission(db, perm.id, permUpdate)
        assert updated.name == "updated_perm_name"

    def test_update_permission_nonexistent(self, db):
        permUpdate = PermissionUpdate(name="should not update")
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.update_permission(db, 99999, permUpdate)
        assert "不存在" in exc_info.value.msg

    def test_delete_permission_normal(self, db):
        permCreate = PermissionCreate(
            name=f"svc_delperm_{uuid.uuid4().hex[:8]}",
            code=f"svc_delperm_code_{uuid.uuid4().hex[:8]}",
            type="api",
        )
        perm = PermissionService.create_permission(db, permCreate)
        result = PermissionService.delete_permission(db, perm.id)
        assert result is True
        found = PermissionService.get_permission_by_id(db, perm.id)
        assert found is None

    def test_delete_permission_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            PermissionService.delete_permission(db, 99999)
        assert "不存在" in exc_info.value.msg

    def test_get_permissions(self, db):
        perms = PermissionService.get_permissions(db, skip=0, limit=10)
        assert isinstance(perms, list)

    def test_create_permission_with_parent(self, db):
        parentCreate = PermissionCreate(
            name=f"svc_parent_{uuid.uuid4().hex[:8]}",
            code=f"svc_parent_code_{uuid.uuid4().hex[:8]}",
            type="menu",
        )
        parent = PermissionService.create_permission(db, parentCreate)
        childCreate = PermissionCreate(
            name=f"svc_child_{uuid.uuid4().hex[:8]}",
            code=f"svc_child_code_{uuid.uuid4().hex[:8]}",
            type="button",
            parent_id=parent.id,
        )
        child = PermissionService.create_permission(db, childCreate)
        assert child.parent_id == parent.id


class TestUserRoleService:
    def test_assign_role_normal(self, db):
        userCreate = UserCreate(
            username=f"svc_assign_{uuid.uuid4().hex[:8]}",
            email=f"svc_assign_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        roleCreate = RoleCreate(
            name=f"svc_assignrole_{uuid.uuid4().hex[:8]}",
            desc="assign test",
        )
        role = RoleService.create_role(db, roleCreate)
        result = UserRoleService.assign_role(db, user.id, role.id)
        assert result is True

    def test_assign_role_duplicate(self, db):
        userCreate = UserCreate(
            username=f"svc_dupassign_{uuid.uuid4().hex[:8]}",
            email=f"svc_dupassign_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        roleCreate = RoleCreate(
            name=f"svc_dupassignrole_{uuid.uuid4().hex[:8]}",
            desc="dup assign",
        )
        role = RoleService.create_role(db, roleCreate)
        UserRoleService.assign_role(db, user.id, role.id)
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, user.id, role.id)
        assert "已分配" in exc_info.value.msg

    def test_assign_role_nonexistent_user(self, db):
        roleCreate = RoleCreate(
            name=f"svc_nouser_{uuid.uuid4().hex[:8]}",
            desc="no user",
        )
        role = RoleService.create_role(db, roleCreate)
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, 99999, role.id)
        assert "用户不存在" in exc_info.value.msg

    def test_assign_role_nonexistent_role(self, db):
        userCreate = UserCreate(
            username=f"svc_norole_{uuid.uuid4().hex[:8]}",
            email=f"svc_norole_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.assign_role(db, user.id, 99999)
        assert "角色不存在" in exc_info.value.msg

    def test_remove_role_normal(self, db):
        userCreate = UserCreate(
            username=f"svc_remove_{uuid.uuid4().hex[:8]}",
            email=f"svc_remove_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        roleCreate = RoleCreate(
            name=f"svc_removerole_{uuid.uuid4().hex[:8]}",
            desc="remove test",
        )
        role = RoleService.create_role(db, roleCreate)
        UserRoleService.assign_role(db, user.id, role.id)
        result = UserRoleService.remove_role(db, user.id, role.id)
        assert result is True

    def test_remove_role_nonexistent(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            UserRoleService.remove_role(db, 99999, 99999)
        assert "不存在" in exc_info.value.msg

    def test_get_user_roles(self, db):
        userCreate = UserCreate(
            username=f"svc_getroles_{uuid.uuid4().hex[:8]}",
            email=f"svc_getroles_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        roles = UserRoleService.get_user_roles(db, user.id)
        assert isinstance(roles, list)


class TestRBACService:
    def test_check_permission_granted(self, db):
        userCreate = UserCreate(
            username=f"svc_rbac_yes_{uuid.uuid4().hex[:8]}",
            email=f"svc_rbac_yes_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        permCode = f"test_perm_{uuid.uuid4().hex[:8]}"
        roleCreate = RoleCreate(
            name=f"svc_rbac_role_{uuid.uuid4().hex[:8]}",
            desc="rbac role",
            permissions=[permCode],
        )
        role = RoleService.create_role(db, roleCreate)
        UserRoleService.assign_role(db, user.id, role.id)
        result = RBACService.check_permission(db, user.id, permCode)
        assert result is True

    def test_check_permission_denied(self, db):
        userCreate = UserCreate(
            username=f"svc_rbac_no_{uuid.uuid4().hex[:8]}",
            email=f"svc_rbac_no_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        result = RBACService.check_permission(db, user.id, "nonexistent_permission_xyz")
        assert result is False

    def test_check_permission_user_no_roles(self, db):
        userCreate = UserCreate(
            username=f"svc_rbac_empty_{uuid.uuid4().hex[:8]}",
            email=f"svc_rbac_empty_{uuid.uuid4().hex[:8]}@test.com",
            password="Test@123456",
        )
        user = UserService.create_user(db, userCreate)
        result = RBACService.check_permission(db, user.id, "any_perm")
        assert result is False
