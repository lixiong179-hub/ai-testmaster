import pytest
from fastapi import status

import app.main
from app.core.permissions import (
    PermissionDenied,
    check_role,
    require_roles,
    ViewPermissions,
    can_view_technical,
    can_edit_locator,
)
from app.models.user import User, Role
from app.utils.jwt_utils import get_password_hash


class TestPermissionDenied:
    def test_default_detail(self):
        exc = PermissionDenied()
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == "权限不足"

    def test_custom_detail(self):
        exc = PermissionDenied(detail="需要管理员权限")
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == "需要管理员权限"

    def test_is_http_exception(self):
        from fastapi import HTTPException
        exc = PermissionDenied()
        assert isinstance(exc, HTTPException)


class TestCheckRole:
    def test_superuser_bypasses_all(self, db):
        user = User(
            username="perm_superuser",
            email="perm_superuser@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
        assert check_role(user, ["admin"]) is True
        assert check_role(user, ["nonexistent"]) is True
        assert check_role(user, []) is True

    def test_user_with_matching_role(self, db):
        user = User(
            username="perm_user_match",
            email="perm_user_match@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="test_engineer", desc="测试工程师")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert check_role(user, ["test_engineer"]) is True
        assert check_role(user, ["test_engineer", "admin"]) is True

    def test_user_without_matching_role(self, db):
        user = User(
            username="perm_user_nomatch",
            email="perm_user_nomatch@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="viewer", desc="观察者")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert check_role(user, ["admin"]) is False
        assert check_role(user, ["test_engineer", "admin"]) is False

    def test_user_with_no_roles(self, db):
        user = User(
            username="perm_user_norole",
            email="perm_user_norole@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        assert check_role(user, ["admin"]) is False
        assert check_role(user, []) is False

    def test_empty_allowed_roles(self, db):
        user = User(
            username="perm_user_empty",
            email="perm_user_empty@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        db.flush()
        assert check_role(user, []) is False

    def test_user_without_is_superuser_attr(self):
        class FakeUser:
            pass
        fake = FakeUser()
        fake.roles = []
        assert check_role(fake, ["admin"]) is False

    def test_user_without_roles_attr(self):
        class FakeUser:
            is_superuser = False
        fake = FakeUser()
        assert check_role(fake, ["admin"]) is False

    def test_user_roles_raises_exception(self):
        class FakeUser:
            is_superuser = False
            @property
            def roles(self):
                raise RuntimeError("db error")
        fake = FakeUser()
        assert check_role(fake, ["admin"]) is False


class TestRequireRoles:
    def test_require_roles_returns_callable(self):
        checker = require_roles(["admin"])
        assert callable(checker)

    def test_require_roles_with_empty_list(self):
        checker = require_roles([])
        assert callable(checker)

    def test_require_roles_with_multiple_roles(self):
        checker = require_roles(["admin", "test_engineer", "developer"])
        assert callable(checker)


class TestViewPermissions:
    def test_business_view_roles(self):
        assert "viewer" in ViewPermissions.BUSINESS_VIEW
        assert "test_engineer" in ViewPermissions.BUSINESS_VIEW
        assert "admin" in ViewPermissions.BUSINESS_VIEW
        assert "developer" in ViewPermissions.BUSINESS_VIEW
        assert "product_manager" in ViewPermissions.BUSINESS_VIEW

    def test_technical_view_roles(self):
        assert "test_engineer" in ViewPermissions.TECHNICAL_VIEW
        assert "admin" in ViewPermissions.TECHNICAL_VIEW
        assert "developer" in ViewPermissions.TECHNICAL_VIEW
        assert "viewer" not in ViewPermissions.TECHNICAL_VIEW
        assert "product_manager" not in ViewPermissions.TECHNICAL_VIEW

    def test_edit_roles(self):
        assert "test_engineer" in ViewPermissions.EDIT
        assert "admin" in ViewPermissions.EDIT
        assert len(ViewPermissions.EDIT) == 2

    def test_admin_roles(self):
        assert ViewPermissions.ADMIN == ["admin"]


class TestCanViewTechnical:
    def test_none_user(self):
        assert can_view_technical(None) is False

    def test_superuser(self, db):
        user = User(
            username="perm_tech_super",
            email="perm_tech_super@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
        assert can_view_technical(user) is True

    def test_user_with_technical_role(self, db):
        user = User(
            username="perm_tech_role",
            email="perm_tech_role@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="developer", desc="开发者")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert can_view_technical(user) is True

    def test_user_without_technical_role(self, db):
        user = User(
            username="perm_tech_norole",
            email="perm_tech_norole@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="viewer", desc="观察者")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert can_view_technical(user) is False


class TestCanEditLocator:
    def test_none_user(self):
        assert can_edit_locator(None) is False

    def test_superuser(self, db):
        user = User(
            username="perm_edit_super",
            email="perm_edit_super@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        db.flush()
        assert can_edit_locator(user) is True

    def test_user_with_edit_role(self, db):
        user = User(
            username="perm_edit_role",
            email="perm_edit_role@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="test_engineer", desc="测试工程师")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert can_edit_locator(user) is True

    def test_user_without_edit_role(self, db):
        user = User(
            username="perm_edit_norole",
            email="perm_edit_norole@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            is_superuser=False,
        )
        role = Role(name="viewer", desc="观察者")
        db.add(user)
        db.add(role)
        db.flush()
        user.roles.append(role)
        db.flush()
        assert can_edit_locator(user) is False
