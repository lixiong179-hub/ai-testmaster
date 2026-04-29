"""
认证模块单元测试
测试JWT工具函数和认证端点
"""
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
    get_password_hash,
    verify_password,
    refresh_access_token
)
from app.core.exception import AuthenticationError


# 创建测试客户端
client = TestClient(app)


class TestJWTUtils:
    """JWT工具函数测试类"""
    
    def test_password_hash(self):
        """测试密码加密和验证"""
        password = "test_password123"
        hashed = get_password_hash(password)
        
        # 验证正确密码
        assert verify_password(password, hashed) is True
        
        # 验证错误密码
        assert verify_password("wrong_password", hashed) is False
    
    def test_create_access_token(self):
        """测试创建访问Token"""
        data = {"sub": "1", "username": "test_user"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        """测试创建刷新Token"""
        data = {"sub": "1", "username": "test_user"}
        token = create_refresh_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_access_token(self):
        """测试验证访问Token"""
        data = {"sub": "1", "username": "test_user"}
        token = create_access_token(data)
        payload = verify_access_token(token)
        
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
    
    def test_verify_refresh_token(self):
        """测试验证刷新Token"""
        data = {"sub": "1", "username": "test_user"}
        token = create_refresh_token(data)
        payload = verify_refresh_token(token)
        
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"
    
    def test_refresh_access_token(self):
        """测试刷新Access Token"""
        data = {"sub": "1"}
        refresh_token = create_refresh_token(data)
        new_access_token = refresh_access_token(refresh_token)
        
        assert new_access_token is not None
        assert isinstance(new_access_token, str)
        
        # 验证新Token有效
        payload = verify_access_token(new_access_token)
        assert payload["sub"] == "1"
    
    def test_invalid_token(self):
        """测试无效Token"""
        with pytest.raises(AuthenticationError):
            verify_access_token("invalid_token")
    
    def test_wrong_token_type(self):
        """测试错误Token类型"""
        # 使用刷新Token作为访问Token
        data = {"sub": "1"}
        refresh_token = create_refresh_token(data)
        
        with pytest.raises(AuthenticationError) as exc_info:
            verify_access_token(refresh_token)
        
        assert "Token类型错误" in str(exc_info.value)


class TestAuthEndpoints:
    """认证端点测试类"""
    
    def test_login_success(self):
        """测试登录成功"""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
    
    def test_login_failure(self):
        """测试登录失败"""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrong_password"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401
    
    def test_register_success(self):
        """测试注册成功"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "password123",
                "confirm_password": "password123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "注册成功"
    
    def test_register_short_password(self):
        """测试注册密码太短"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "new_user",
                "email": "new_user@example.com",
                "password": "123",
                "confirm_password": "123"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == 400
    
    def test_get_current_user(self):
        """测试获取当前用户信息"""
        # 先登录获取Token
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin"}
        )
        token = login_response.json()["data"]["access_token"]
        
        # 使用Token获取用户信息
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["username"] == "admin"
    
    def test_get_current_user_invalid_token(self):
        """测试使用无效Token获取用户信息"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401


class TestHealthEndpoint:
    """健康检查端点测试类"""
    
    def test_health_check(self):
        """测试健康检查接口"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
    
    def test_root_endpoint(self):
        """测试根路径接口"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
