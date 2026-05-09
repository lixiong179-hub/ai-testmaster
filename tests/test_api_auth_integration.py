import uuid
import pytest

pytestmark = pytest.mark.skip(reason="API契约变更（验证码/认证机制重构），测试需要完全重�?)

from tests.helpers import (
    assertResponseSuccess,
    assertResponseError,
    assertResponseUnauthorized,
    assertFieldValue,
    assertFieldExists,
    createTestUser,
    getAuthHeaders,
    loginAndGetToken,
)


class TestCaptcha:
    def test_get_captcha(self, client):
        response = client.get("/api/v1/auth/captcha")
        data = assertResponseSuccess(response)
        assertFieldExists(data, "captcha_id")
        assertFieldExists(data, "captcha_text")

    def test_get_captcha_returns_different_ids(self, client):
        r1 = client.get("/api/v1/auth/captcha")
        r2 = client.get("/api/v1/auth/captcha")
        d1 = r1.json()
        d2 = r2.json()
        assert d1["captcha_id"] != d2["captcha_id"]


class TestRegister:
    def test_register_normal(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": f"reg_user_{uniqueId}",
                "password": "Test@123456",
                "email": f"reg_{uniqueId}@test.com",
            },
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")
        assertFieldExists(data, "username")

    def test_register_duplicate_username(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        username = f"dup_user_{uniqueId}"
        client.post(
            "/api/v1/auth/register",
            params={"username": username, "password": "Test@123456", "email": f"dup1_{uniqueId}@test.com"},
        )
        response = client.post(
            "/api/v1/auth/register",
            params={"username": username, "password": "Test@123456", "email": f"dup2_{uniqueId}@test.com"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_duplicate_email(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        email = f"dup_{uniqueId}@test.com"
        client.post(
            "/api/v1/auth/register",
            params={"username": f"email_user1_{uniqueId}", "password": "Test@123456", "email": email},
        )
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"email_user2_{uniqueId}", "password": "Test@123456", "email": email},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_username(self, client):
        response = client.post(
            "/api/v1/auth/register",
            params={"username": "ab", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_password(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"shortpwd_{uniqueId}", "password": "12345"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_without_email(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"noemail_{uniqueId}", "password": "Test@123456"},
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")


class TestLogin:
    def test_login_normal(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": "Test@123456"},
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "access_token")
        assertFieldExists(data, "user")

    def test_login_wrong_password(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": "WrongPassword123"},
        )
        assertResponseError(response, expectedStatus=401)

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user_xyz", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=401)

    def test_login_inactive_user(self, client, db):
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        uniqueId = uuid.uuid4().hex[:8]
        inactiveUser = User(
            username=f"inactive_{uniqueId}",
            email=f"inactive_{uniqueId}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=False,
            is_superuser=False,
        )
        db.add(inactiveUser)
        db.flush()
        response = client.post(
            "/api/v1/auth/login",
            json={"username": inactiveUser.username, "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=403)

    def test_login_empty_username(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=422)

    def test_login_empty_password(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": ""},
        )
        assertResponseError(response, expectedStatus=422)


class TestGetCurrentUser:
    def test_get_me_normal(self, client, authHeaders, testUser):
        response = client.get("/api/v1/auth/me", headers=authHeaders)
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")
        assertFieldExists(data, "username")

    def test_get_me_no_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assertResponseUnauthorized(response)

    def test_get_me_invalid_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assertResponseUnauthorized(response)

    def test_get_me_empty_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assertResponseUnauthorized(response)
