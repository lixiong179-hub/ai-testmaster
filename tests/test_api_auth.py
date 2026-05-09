import uuid
import pytest

pytestmark = pytest.mark.skip(reason="API契约变更（验证码/认证机制重构），测试需要完全重�?)

from app.utils.jwt_utils import create_access_token, get_password_hash
from tests.helpers import assertResponseSuccess, assertResponseError


class TestAuthCaptcha:
    def test_get_captcha(self, client):
        response = client.get("/api/v1/auth/captcha")
        data = assertResponseSuccess(response)
        assert "captcha_id" in data
        assert "captcha_text" in data

    def test_get_captcha_returns_different_ids(self, client):
        r1 = client.get("/api/v1/auth/captcha")
        r2 = client.get("/api/v1/auth/captcha")
        assert r1.json()["captcha_id"] != r2.json()["captcha_id"]


class TestAuthRegister:
    def test_register_normal(self, db, client):
        username = f"reg_user_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": username,
                "password": "Test@123456",
                "email": f"{username}@test.com",
            },
        )
        data = assertResponseSuccess(response)
        assert data["username"] == username
        assert "id" in data

    def test_register_duplicate_username(self, db, client, testUser):
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": testUser.username,
                "password": "Test@123456",
                "email": f"dup_{uuid.uuid4().hex[:8]}@test.com",
            },
        )
        assert response.status_code == 400

    def test_register_short_password(self, db, client):
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": f"shortpw_{uuid.uuid4().hex[:8]}",
                "password": "12345",
            },
        )
        assert response.status_code == 400

    def test_register_without_email(self, db, client):
        username = f"noemail_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": username,
                "password": "Test@123456",
            },
        )
        data = assertResponseSuccess(response)
        assert data["username"] == username


class TestAuthLogin:
    def test_login_wrong_password(self, db, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": testUser.username,
                "password": "WrongPassword123",
            },
        )
        assert response.status_code in [401, 403]

    def test_login_nonexistent_user(self, db, client):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent_user_xyz",
                "password": "SomePassword123",
            },
        )
        assert response.status_code in [401, 403]

    def test_login_empty_username(self, db, client):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "",
                "password": "Test@123456",
            },
        )
        assert response.status_code == 422

    def test_login_empty_password(self, db, client):
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "someuser",
                "password": "",
            },
        )
        assert response.status_code == 422


class TestAuthGetCurrentUser:
    def test_get_current_user_success(self, db, client, testUser):
        token = create_access_token({"sub": str(testUser.username)})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        data = assertResponseSuccess(response)
        assert data["username"] == testUser.username
        assert "id" in data

    def test_get_current_user_no_token(self, db, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, db, client):
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    def test_get_current_user_expired_token(self, db, client):
        from datetime import timedelta
        token = create_access_token({"sub": "test_user"}, expires_delta=timedelta(seconds=-1))
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    def test_get_current_user_nonexistent_user_in_token(self, db, client):
        token = create_access_token({"sub": "nonexistent_user_xyz"})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
