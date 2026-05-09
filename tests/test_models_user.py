import pytest
from datetime import datetime
from app.models.user import User, Role, Permission
from app.models.test_task import TaskStatus


class TestUserModel:
    def test_create_user(self, db):
        user = User(username="model_test_user", email="model_test@example.com", password_hash="hashed_pwd_123")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.username == "model_test_user"
        assert user.email == "model_test@example.com"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.create_time is not None
        db.delete(user)
        db.commit()

    def test_user_default_values(self, db):
        user = User(username="default_user", email="default@example.com", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.login_count == 0
        assert user.failed_login_attempts == 0
        assert user.phone is None
        assert user.last_login_time is None
        assert user.external_id is None
        assert user.external_system is None
        assert user.locked_until is None
        db.delete(user)
        db.commit()

    def test_user_security_fields(self, db):
        user = User(username="security_user", email="security@example.com", password_hash="hash", failed_login_attempts=3, external_id="ldap_001", external_system="LDAP")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.failed_login_attempts == 3
        assert user.external_id == "ldap_001"
        assert user.external_system == "LDAP"
        db.delete(user)
        db.commit()

    def test_user_unique_username(self, db):
        user1 = User(username="unique_user_test", email="unique1@example.com", password_hash="hash")
        db.add(user1)
        db.commit()
        nested = db.begin_nested()
        user2 = User(username="unique_user_test", email="unique2@example.com", password_hash="hash")
        db.add(user2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_user_unique_email(self, db):
        user1 = User(username="email_user1", email="same_email@example.com", password_hash="hash")
        db.add(user1)
        db.commit()
        nested = db.begin_nested()
        user2 = User(username="email_user2", email="same_email@example.com", password_hash="hash")
        db.add(user2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_user_nullable_fields(self, db):
        user = User(username="nullable_user", email="nullable@example.com", password_hash="hash", phone="13800138000", last_login_time=datetime(2024, 1, 1, 12, 0, 0), locked_until=datetime(2024, 12, 31, 23, 59, 59))
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.phone == "13800138000"
        assert user.last_login_time == datetime(2024, 1, 1, 12, 0, 0)
        assert user.locked_until == datetime(2024, 12, 31, 23, 59, 59)
        db.delete(user)
        db.commit()

    def test_user_relationships_exist(self):
        assert hasattr(User, 'projects')
        assert hasattr(User, 'test_tasks')
        assert hasattr(User, 'roles')


class TestRoleModel:
    def test_create_role(self, db):
        role = Role(name="test_role_model", desc="测试角色")
        db.add(role)
        db.commit()
        db.refresh(role)
        assert role.id is not None
        assert role.name == "test_role_model"
        assert role.desc == "测试角色"
        assert role.create_time is not None
        db.delete(role)
        db.commit()

    def test_role_with_permissions(self, db):
        role = Role(name="perm_role_model", desc="带权限角�?, permissions=["read", "write"])
        db.add(role)
        db.commit()
        db.refresh(role)
        assert role.permissions == ["read", "write"]
        db.delete(role)
        db.commit()

    def test_role_nullable_fields(self, db):
        role = Role(name="null_role_model")
        db.add(role)
        db.commit()
        db.refresh(role)
        assert role.desc is None
        assert role.permissions is None
        db.delete(role)
        db.commit()

    def test_role_unique_name(self, db):
        role1 = Role(name="unique_role_model")
        db.add(role1)
        db.commit()
        nested = db.begin_nested()
        role2 = Role(name="unique_role_model")
        db.add(role2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()


class TestPermissionModel:
    def test_create_permission(self, db):
        perm = Permission(name="测试权限", code="test_perm_model", type="api", action="read")
        db.add(perm)
        db.commit()
        db.refresh(perm)
        assert perm.id is not None
        assert perm.name == "测试权限"
        assert perm.code == "test_perm_model"
        assert perm.type == "api"
        assert perm.action == "read"
        db.delete(perm)
        db.commit()

    def test_permission_default_type(self, db):
        perm = Permission(name="默认类型权限", code="default_type_perm")
        db.add(perm)
        db.commit()
        db.refresh(perm)
        assert perm.type == "api"
        db.delete(perm)
        db.commit()

    def test_permission_nullable_fields(self, db):
        perm = Permission(name="最小权�?, code="minimal_perm")
        db.add(perm)
        db.commit()
        db.refresh(perm)
        assert perm.resource_type is None
        assert perm.action is None
        assert perm.parent_id is None
        assert perm.description is None
        db.delete(perm)
        db.commit()

    def test_permission_self_reference(self, db):
        parent = Permission(name="父权�?, code="parent_perm_model")
        db.add(parent)
        db.commit()
        db.refresh(parent)
        child = Permission(name="子权�?, code="child_perm_model", parent_id=parent.id)
        db.add(child)
        db.commit()
        db.refresh(child)
        assert child.parent_id == parent.id
        db.delete(child)
        db.delete(parent)
        db.commit()

    def test_permission_unique_code(self, db):
        perm1 = Permission(name="唯一1", code="unique_code_perm")
        db.add(perm1)
        db.commit()
        nested = db.begin_nested()
        perm2 = Permission(name="唯一2", code="unique_code_perm")
        db.add(perm2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()


class TestTaskStatus:
    def test_pending(self):
        assert TaskStatus.PENDING == 0

    def test_running(self):
        assert TaskStatus.RUNNING == 1

    def test_completed(self):
        assert TaskStatus.COMPLETED == 2

    def test_failed(self):
        assert TaskStatus.FAILED == 3

    def test_stopped(self):
        assert TaskStatus.STOPPED == 4

    def test_labels(self):
        assert TaskStatus.LABELS[0] == "等待执行"
        assert TaskStatus.LABELS[1] == "执行�?
        assert TaskStatus.LABELS[2] == "执行完成"
        assert TaskStatus.LABELS[3] == "执行失败"
        assert TaskStatus.LABELS[4] == "已停�?

    def test_labels_completeness(self):
        assert len(TaskStatus.LABELS) == 5
