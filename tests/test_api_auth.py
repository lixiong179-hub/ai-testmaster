"""认证 API 端点测试

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

from app.utils.jwt_utils import create_access_token, get_password_hash
from tests.helpers import assertResponseSuccess, assertResponseError


def _getCaptcha(client) -> tuple[str, str]:
    """获取验证码, 返回 (captcha_id, captcha_code)。"""
    response = client.get("/api/v1/auth/captcha")
    data = assertResponseSuccess(response)["data"]
    return data["captcha_id"], data["code"]


class TestAuthCaptcha:
    def test_get_captcha(self, client):
        response = client.get("/api/v1/auth/captcha")
        data = assertResponseSuccess(response)["data"]
        assert "captcha_id" in data
        assert "code" in data  # 当前字段名为 code, 非 captcha_text

    def test_get_captcha_returns_different_ids(self, client):
        r1 = client.get("/api/v1/auth/captcha")
        r2 = client.get("/api/v1/auth/captcha")
        assert r1.json()["data"]["captcha_id"] != r2.json()["data"]["captcha_id"]


class TestAuthRegister:
    def test_register_normal(self, db, client):
        username = f"reg_user_{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"{username}@test.com",
            },
        )
        data = assertResponseSuccess(response)["data"]
        assert data["username"] == username
        assert "id" in data

    def test_register_duplicate_username(self, db, client, testUser):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": testUser.username,
                "password": "Test@123456",
                "confirm_password": "Test@123456",
                "email": f"dup_{uuid.uuid4().hex[:8]}@test.com",
            },
        )
        assert response.status_code == 400

    def test_register_short_password(self, db, client):
        # Pydantic 校验失败被全局异常处理器包装为 400 (含 errors 详情)
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"shortpw_{uuid.uuid4().hex[:8]}",
                "password": "12345",
                "confirm_password": "12345",
                "email": f"short_{uuid.uuid4().hex[:8]}@test.com",
            },
        )
        assert response.status_code == 400
        # 响应体含 Pydantic 校验错误详情
        body = response.json()
        assert "errors" in body.get("data", {}) or "errors" in str(body)

    def test_register_without_email(self, db, client):
        # RegisterRequest schema 中 email 为必填 (EmailStr), 缺失返回 400 (全局异常处理器包装)
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"noemail_{uuid.uuid4().hex[:8]}",
                "password": "Test@123456",
                "confirm_password": "Test@123456",
            },
        )
        assert response.status_code == 400


class TestAuthLogin:
    def test_login_wrong_password(self, db, client, testUser):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": testUser.username,
                "password": "WrongPassword123",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code in [401, 403]

    def test_login_nonexistent_user(self, db, client):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent_user_xyz",
                "password": "SomePassword123",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code in [401, 403]

    def test_login_empty_username(self, db, client):
        # 登录端点支持 JSON body, empty username 触发 400 "请提供用户名和密码"
        # (不是 422, 因为端点用 Form/JSON 解析而非 Pydantic schema 校验)
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
        assert response.status_code == 400

    def test_login_empty_password(self, db, client, testUser):
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
        assert response.status_code == 400

    def test_login_missing_captcha(self, db, client, testUser):
        """未提供 captcha 时应返回 400 '请提供验证码'。"""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": "Test@123456"},
        )
        assert response.status_code == 400
        # 异常处理器返回 message/detail 字段, 兼容两种
        body = response.json()
        assert "验证码" in body.get("detail", "") or "验证码" in body.get("message", "")

    def test_login_wrong_captcha(self, db, client, testUser):
        """captcha_code 错误应返回 401 '验证码错误或已过期'。"""
        captcha_id, _ = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": testUser.username,
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": "WRONG_CODE",
            },
        )
        assert response.status_code == 401

    def test_login_success(self, db, client, testUser):
        """完整登录流程: 获取 captcha → 登录 → 返回 access_token。"""
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": testUser.username,
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        data = assertResponseSuccess(response)["data"]
        assert "access_token" in data
        assert data["user"]["username"] == testUser.username


class TestAuthGetCurrentUser:
    def test_get_current_user_success(self, db, client, testUser):
        # token sub 必须为 user.id (非 username), 否则 me 端点查询失败返回 401
        token = create_access_token(
            {"sub": str(testUser.id), "username": testUser.username}
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        data = assertResponseSuccess(response)["data"]
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
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=-1)
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    def test_get_current_user_nonexistent_user_in_token(self, db, client):
        # sub 指向不存在的 user.id, me 端点应返回 401
        token = create_access_token({"sub": "999999", "username": "ghost"})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
