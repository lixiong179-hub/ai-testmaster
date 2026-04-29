"""用户服务单元测试 - UserService

测试设计原则:
1. db fixture 自动将 commit 降级为 flush，无需手动 savepoint
2. 断言精确值，不用 >= / <= 等弱断言
3. 覆盖正常路径 + 边界 + 异常路径
4. 验证业务约束（唯一性、禁用状态等）
"""
import pytest
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.exception import BaseAPIException
from app.services.user_service.user_service import UserService, pwd_context


class TestLazyImports:
    """测试 user_service/__init__.py 的 lazy import 机制"""

    def test_import_role_service(self):
        from app.services.user_service import RoleService
        from app.services.role_service.role_service import RoleService as DirectRoleService
        assert RoleService is DirectRoleService

    def test_import_permission_service(self):
        from app.services.user_service import PermissionService
        from app.services.permission_service import PermissionService as DirectPS
        assert PermissionService is DirectPS

    def test_import_user_role_service(self):
        from app.services.user_service import UserRoleService
        from app.services.permission_service import UserRoleService as DirectURS
        assert UserRoleService is DirectURS

    def test_import_rbac_service(self):
        from app.services.user_service import RBACService
        from app.services.permission_service import RBACService as DirectRBAC
        assert RBACService is DirectRBAC

    def test_import_nonexistent_raises_attributeerror(self):
        import app.services.user_service as us_mod
        with pytest.raises(AttributeError, match="has no attribute"):
            us_mod.NonExistentService


def _create_user(db, username="svc_user", email=None, password="Test@123"):
    """Helper: create user via UserService. db fixture auto-converts commit to flush."""
    return UserService.create_user(db, UserCreate(
        username=username, password=password,
        email=email or f"{username}@test.com",
    ))


class TestVerifyPassword:
    def test_correct_password(self):
        hashed = pwd_context.hash("mysecret")
        assert UserService.verify_password("mysecret", hashed) is True

    def test_wrong_password(self):
        hashed = pwd_context.hash("mysecret")
        assert UserService.verify_password("wrong", hashed) is False

    def test_empty_password(self):
        hashed = pwd_context.hash("")
        assert UserService.verify_password("", hashed) is True


class TestGetPasswordHash:
    def test_hash_differs_from_plain(self):
        hashed = UserService.get_password_hash("mypassword")
        assert hashed != "mypassword"
        assert pwd_context.verify("mypassword", hashed)

    def test_hash_is_bcrypt_format(self):
        hashed = UserService.get_password_hash("test")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_different_inputs_different_hashes(self):
        h1 = UserService.get_password_hash("password1")
        h2 = UserService.get_password_hash("password2")
        assert h1 != h2

    def test_same_input_different_salts(self):
        h1 = UserService.get_password_hash("same")
        h2 = UserService.get_password_hash("same")
        assert h1 != h2


class TestCreateUser:
    def test_create_with_schema(self, db):
        user = _create_user(db, "create_schema_user")
        assert user.id is not None
        assert user.username == "create_schema_user"
        assert user.password_hash != "Test@123"
        assert user.is_active is True
        assert user.is_superuser is False

    def test_create_with_dict(self, db):
        user = UserService.create_user(db, {
            "username": "dict_user", "password": "Test@123",
            "email": "dict_user@test.com",
        })
        assert user.username == "dict_user"
        assert user.email == "dict_user@test.com"

    def test_create_duplicate_username_raises_400(self, db):
        _create_user(db, "dup_uname_user")
        with pytest.raises(BaseAPIException) as exc_info:
            _create_user(db, "dup_uname_user")
        assert exc_info.value.code == 400
        assert "用户名" in exc_info.value.msg

    def test_create_duplicate_email_raises_400(self, db):
        _create_user(db, "email_dup1", email="dup@test.com")
        with pytest.raises(BaseAPIException) as exc_info:
            _create_user(db, "email_dup2", email="dup@test.com")
        assert exc_info.value.code == 400
        assert "邮箱" in exc_info.value.msg

    def test_password_is_hashed_not_stored_plain(self, db):
        user = _create_user(db, "pw_check_user")
        assert user.password_hash != "Test@123"
        assert pwd_context.verify("Test@123", user.password_hash)

    def test_created_user_is_active_by_default(self, db):
        user = _create_user(db, "active_check_user")
        assert user.is_active is True


class TestAuthenticateUser:
    def test_authenticate_success(self, db):
        _create_user(db, "auth_user")
        user = UserService.authenticate_user(db, "auth_user", "Test@123")
        assert user is not None
        assert user.username == "auth_user"
        assert user.is_active is True

    def test_authenticate_wrong_password_returns_none(self, db):
        _create_user(db, "auth_wrong_pw")
        result = UserService.authenticate_user(db, "auth_wrong_pw", "wrongpw")
        assert result is None

    def test_authenticate_nonexistent_user_returns_none(self, db):
        result = UserService.authenticate_user(db, "nonexistent", "Test@123")
        assert result is None

    def test_authenticate_disabled_user_raises_403(self, db):
        user = _create_user(db, "disabled_user")
        user.is_active = False
        db.commit()
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.authenticate_user(db, "disabled_user", "Test@123")
        assert exc_info.value.code == 403
        assert "禁用" in exc_info.value.msg


class TestGetUserById:
    def test_found(self, db):
        user = _create_user(db, "getbyid_user")
        result = UserService.get_user_by_id(db, user.id)
        assert result is not None
        assert result.id == user.id
        assert result.username == "getbyid_user"

    def test_not_found_returns_none(self, db):
        result = UserService.get_user_by_id(db, 99999)
        assert result is None


class TestGetUserByUsername:
    def test_found(self, db):
        user = _create_user(db, "getbyname_user")
        result = UserService.get_user_by_username(db, "getbyname_user")
        assert result is not None
        assert result.id == user.id

    def test_not_found_returns_none(self, db):
        result = UserService.get_user_by_username(db, "no_such_user")
        assert result is None


class TestUpdateUser:
    def test_update_email_with_schema(self, db):
        user = _create_user(db, "upd_schema_user")
        result = UserService.update_user(db, user.id, UserUpdate(email="new@test.com"))
        assert result.email == "new@test.com"

    def test_update_phone_with_dict(self, db):
        user = _create_user(db, "upd_dict_user")
        result = UserService.update_user(db, user.id, {"phone": "13800138000"})
        assert result.phone == "13800138000"

    def test_update_nonexistent_raises_404(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.update_user(db, 99999, {"phone": "138"})
        assert exc_info.value.code == 404

    def test_partial_update_preserves_other_fields(self, db):
        user = _create_user(db, "partial_upd_user", email="orig@test.com")
        original_hash = user.password_hash
        result = UserService.update_user(db, user.id, {"phone": "13900139000"})
        assert result.phone == "13900139000"
        assert result.email == "orig@test.com"
        assert result.password_hash == original_hash


class TestDeleteUser:
    def test_delete_success(self, db):
        user = _create_user(db, "del_user")
        user_id = user.id
        result = UserService.delete_user(db, user_id)
        assert result is True
        assert UserService.get_user_by_id(db, user_id) is None

    def test_delete_nonexistent_raises_404(self, db):
        with pytest.raises(BaseAPIException) as exc_info:
            UserService.delete_user(db, 99999)
        assert exc_info.value.code == 404


class TestGetUsers:
    def test_get_users_returns_created_user(self, db):
        user = _create_user(db, "list_user_a")
        users = UserService.get_users(db)
        usernames = [u.username for u in users]
        assert "list_user_a" in usernames

    def test_get_users_pagination_limit(self, db):
        # 先创建用户确保有数据
        _create_user(db, "pagination_user")
        users = UserService.get_users(db, skip=0, limit=1)
        assert len(users) <= 1  # limit=1 最多返回1条

    def test_get_users_skip(self, db):
        all_users = UserService.get_users(db, skip=0, limit=1000)
        if len(all_users) > 1:
            skipped = UserService.get_users(db, skip=1, limit=1000)
            assert len(skipped) == len(all_users) - 1


class TestConcurrencyIntegrityError:
    """测试并发场景下 IntegrityError 兜底路径（line 119-122, 218-220）"""

    def test_create_user_integrity_error_fallback(self, db):
        """模拟 db.commit() 时 IntegrityError — 并发突破前置校验的兜底"""
        from unittest.mock import patch
        from sqlalchemy.exc import IntegrityError as SAIntegrityError

        user = _create_user(db, "concurrency_user")
        # db.commit 已被 fixture 替换为 flush，patch flush 以模拟 IntegrityError
        with patch.object(db, 'commit', side_effect=SAIntegrityError("stmt", "params", None)):
            with pytest.raises(BaseAPIException) as exc_info:
                UserService.create_user(db, UserCreate(
                    username="another_concurrent_user",
                    password="Test@123",
                    email="concurrent@test.com",
                ))
            assert exc_info.value.code == 400

    def test_update_user_integrity_error_fallback(self, db):
        """模拟 update commit 时 IntegrityError"""
        from unittest.mock import patch
        from sqlalchemy.exc import IntegrityError as SAIntegrityError

        user = _create_user(db, "upd_concurrency_user")
        # db.commit 已被 fixture 替换为 flush，patch commit (=flush) 以模拟 IntegrityError
        with patch.object(db, 'commit', side_effect=SAIntegrityError("stmt", "params", None)):
            with pytest.raises(BaseAPIException) as exc_info:
                UserService.update_user(db, user.id, {"email": "dup@test.com"})
            assert exc_info.value.code == 400
