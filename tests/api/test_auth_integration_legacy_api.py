"""认证 API 集成测试

覆盖范围:
    - GET  /api/v1/auth/captcha        - 获取验证码
    - POST /api/v1/auth/register       - 用户注册 (JSON body RegisterRequest)
    - POST /api/v1/auth/login          - 用户登录 (需 captcha_id + captcha_code)
    - GET  /api/v1/auth/me             - 获取当前用户 (Bearer token)

契约要点:
    - captcha 端点返回 {captcha_id, code} (非 captcha_text)
    - register 端点接受 JSON body, 需 username/email/password/confirm_password
    - login 端点必传 captcha_id + captcha_code, 否则 400 "请提供验证码"
    - me 端点 token sub 为 user.id (非 username)
"""
import uuid
import pytest

# pytestmark = pytest.mark.skip(reason="API契约变更（验证码/认证机制重构），测试需要完全重写")  # 临时移除排查

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


def _getCaptcha(client) -> tuple[str, str]:
    """获取验证码, 返回 (captcha_id, captcha_code)。"""
    response = client.get("/api/v1/auth/captcha")
    data = assertResponseSuccess(response)["data"]
    return data["captcha_id"], data["code"]


def _loginWithCaptcha(client, username: str, password: str):
    """完整登录流程: 获取 captcha → 登录。返回 response 对象。"""
    captcha_id, captcha_code = _getCaptcha(client)
    return client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
            "captcha_id": captcha_id,
            "captcha_code": captcha_code,
        },
    )


class TestCaptcha:
    def test_get_captcha(self, client):
        response = client.get("/api/v1/auth/captcha")
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "captcha_id")
        assertFieldExists(data, "code")  # 当前字段为 code, 非 captcha_text

    def test_get_captcha_returns_different_ids(self, client):
        r1 = client.get("/api/v1/auth/captcha")
        r2 = client.get("/api/v1/auth/captcha")
        d1 = r1.json()["data"]
        d2 = r2.json()["data"]
        assert d1["captcha_id"] != d2["captcha_id"]


class TestRegister:
    def test_register_normal(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"reg_user_{uniqueId}",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"reg_{uniqueId}@test.com",
            },
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")
        assertFieldExists(data, "username")

    def test_register_duplicate_username(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        username = f"dup_user_{uniqueId}"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"dup1_{uniqueId}@test.com",
            },
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"dup2_{uniqueId}@test.com",
            },
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_duplicate_email(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        email = f"dup_{uniqueId}@test.com"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": f"email_user1_{uniqueId}",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": email,
            },
        )
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"email_user2_{uniqueId}",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": email,
            },
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_username(self, client):
        # Pydantic min_length=3 校验失败被全局异常处理器包装为 400
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "ab",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"shortu_{uuid.uuid4().hex[:8]}@test.com",
            },
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_password(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"shortpwd_{uniqueId}",
                "password": "12345",
                "confirm_password": "12345",
                "email": f"short_{uniqueId}@test.com",
            },
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_without_email(self, client):
        # RegisterRequest schema email 为必填 (EmailStr), 缺失返回 400
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"noemail_{uniqueId}",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
            },
        )
        assertResponseError(response, expectedStatus=400)


class TestLogin:
    def test_login_normal(self, client, testUser):
        response = _loginWithCaptcha(client, testUser.username, "Test@123456")
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "access_token")
        assertFieldExists(data, "user")

    def test_login_wrong_password(self, client, testUser):
        response = _loginWithCaptcha(client, testUser.username, "WrongPassword123")
        assertResponseError(response, expectedStatus=401)

    def test_login_nonexistent_user(self, client):
        response = _loginWithCaptcha(client, "nonexistent_user_xyz", "Test@123456")
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
        response = _loginWithCaptcha(client, inactiveUser.username, "Test@123456")
        assertResponseError(response, expectedStatus=403)

    def test_login_empty_username(self, client):
        # 端点解析 JSON body, empty username 触发 400 "请提供用户名和密码"
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "",
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assertResponseError(response, expectedStatus=400)

    def test_login_empty_password(self, client, testUser):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": testUser.username,
                "password": "",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assertResponseError(response, expectedStatus=400)


class TestGetCurrentUser:
    def test_get_me_normal(self, client, authHeaders, testUser):
        response = client.get("/api/v1/auth/me", headers=authHeaders)
        data = assertResponseSuccess(response)["data"]
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
