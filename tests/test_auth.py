"""
认证模块单元测试

测试范围:
- JWT工具函数（密码哈希、令牌创建/验证/刷新、异常处理）
- 认证端点（登录Form/JSON、注册、获取当前用户、验证码）
- 安全边界（禁用账户、重复注册、密码不一致、过期令牌）
"""
import pytest
from datetime import timedelta

from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
    get_password_hash,
    verify_password,
    refresh_access_token,
)
from app.core.exception import AuthenticationError


def _getCaptcha(client) -> tuple[str, str]:
    """获取验证码, 返回 (captcha_id, captcha_code)。

    登录端点要求 captcha_id + captcha_code, 通过 GET /api/v1/auth/captcha 获取。
    """
    response = client.get("/api/v1/auth/captcha")
    assert response.status_code == 200, (
        f"获取验证码失败: status={response.status_code}, body={response.text}"
    )
    body = response.json()
    data = body["data"] if "data" in body else body
    assert "captcha_id" in data and "code" in data, (
        f"验证码响应缺少必要字段: body={body}"
    )
    return data["captcha_id"], data["code"]


class TestJWTUtils:

    def test_password_hash_and_verify(self):
        password = "SecureP@ss123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_create_access_token(self):
        data = {"sub": "1", "username": "test_user"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        data = {"sub": "1", "username": "test_user"}
        token = create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token(self):
        data = {"sub": "1", "username": "test_user"}
        token = create_access_token(data)
        payload = verify_access_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "access"

    def test_verify_refresh_token(self):
        data = {"sub": "1", "username": "test_user"}
        token = create_refresh_token(data)
        payload = verify_refresh_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"

    def test_refresh_access_token(self):
        data = {"sub": "1"}
        refresh_token = create_refresh_token(data)
        new_access_token = refresh_access_token(refresh_token)
        assert isinstance(new_access_token, str)
        payload = verify_access_token(new_access_token)
        assert payload["sub"] == "1"

    def test_invalid_token_raises_auth_error(self):
        with pytest.raises(AuthenticationError):
            verify_access_token("invalid_token_string")

    def test_wrong_token_type_raises_auth_error(self):
        refresh_token = create_refresh_token({"sub": "1"})
        with pytest.raises(AuthenticationError) as exc_info:
            verify_access_token(refresh_token)
        assert "Token类型错误" in str(exc_info.value)


class TestLoginEndpoint:

    def test_login_success_form(self, client, testUser):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": testUser.username,
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert "access_token" in body["data"]
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["user"]["username"] == testUser.username
        assert body["data"]["user"]["is_active"] is True

    def test_login_success_json(self, client, testUser):
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
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert "access_token" in body["data"]

    def test_login_wrong_password(self, client, testUser):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": testUser.username,
                "password": "WrongPass!1",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == 401

    def test_login_nonexistent_user(self, client):
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent_user_xyz",
                "password": "Whatever123",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == 401

    def test_login_missing_username(self, client):
        # 提供 captcha 但缺 username, 端点返回 400 "请提供用户名和密码"
        # 用 json 调用走 JSON 路径, 避免 form data 触发 "Stream consumed"
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 400

    def test_login_missing_password(self, client):
        # 提供 captcha 但缺 password, 端点返回 400 "请提供用户名和密码"
        # 用 json 调用走 JSON 路径, 避免 form data 触发 "Stream consumed"
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "some_user",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 400

    def test_login_disabled_account(self, client, db, testUser):
        testUser.is_active = False
        db.flush()
        captcha_id, captcha_code = _getCaptcha(client)
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": testUser.username,
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert body["code"] == 403


class TestRegisterEndpoint:

    async def test_register_success(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "reg_new_user",
                "email": "reg_new@test.com",
                "password": "RegPass@123",
                "confirm_password": "RegPass@123",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert body["data"]["username"] == "reg_new_user"
        assert body["data"]["message"] == "注册成功"

    async def test_register_duplicate_username(self, async_client, async_test_user):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": async_test_user.username,
                "email": "another_email@test.com",
                "password": "Pass@123456",
                "confirm_password": "Pass@123456",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert "用户名已存在" in body["message"]

    async def test_register_duplicate_email(self, async_client, async_test_user):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "unique_new_user_xyz",
                "email": async_test_user.email,
                "password": "Pass@123456",
                "confirm_password": "Pass@123456",
            },
        )
        assert response.status_code == 400
        body = response.json()
        assert "邮箱已被注册" in body["message"]

    async def test_register_short_password(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "short_pw_user",
                "email": "short_pw@test.com",
                "password": "123",
                "confirm_password": "123",
            },
        )
        assert response.status_code == 400

    async def test_register_password_mismatch(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "mismatch_user",
                "email": "mismatch@test.com",
                "password": "Password@123",
                "confirm_password": "Different@456",
            },
        )
        assert response.status_code == 400

    async def test_register_short_username(self, async_client):
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "username": "ab",
                "email": "short_name@test.com",
                "password": "Pass@123456",
                "confirm_password": "Pass@123456",
            },
        )
        assert response.status_code == 400


class TestMeEndpoint:

    def test_get_current_user_success(self, client, testUser):
        # 先通过完整 captcha 流程登录获取 access_token
        captcha_id, captcha_code = _getCaptcha(client)
        login_resp = client.post(
            "/api/v1/auth/login",
            data={
                "username": testUser.username,
                "password": "Test@123456",
                "captcha_id": captcha_id,
                "captcha_code": captcha_code,
            },
        )
        token = login_resp.json()["data"]["access_token"]
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert body["data"]["username"] == testUser.username
        assert body["data"]["email"] == testUser.email
        assert "password_hash" not in str(body["data"])

    def test_get_current_user_invalid_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_get_current_user_missing_token(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_current_user_expired_token(self, client, testUser):
        expired_token = create_access_token(
            {"sub": str(testUser.id), "username": testUser.username},
            expires_delta=timedelta(seconds=-1),
        )
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401


class TestCaptchaEndpoint:

    async def test_get_captcha(self, async_client):
        response = await async_client.get("/api/v1/auth/captcha")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert "captcha_id" in body["data"]
        assert "code" in body["data"]

    async def test_get_captcha_generate_alias(self, async_client):
        response = await async_client.get("/api/v1/auth/captcha/generate")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert "captcha_id" in body["data"]


class TestHealthEndpoint:

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # /health 端点直接返回 dict (无 create_response 包装), status 可能为 healthy 或 degraded
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
        assert "services" in data

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
