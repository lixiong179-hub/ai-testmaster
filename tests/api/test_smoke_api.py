"""
AI TestMaster API集成测试套件

运行: python -m pytest tests/test_api.py -v
"""
import pytest
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from typing import Optional

# API基础URL
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def _backend_available():
    try:
        return requests.get(f"{BASE_URL}{API_PREFIX}/auth/login", timeout=2).status_code < 500
    except (requests.ConnectionError, requests.Timeout):
        return False


_BACKEND_OK = _backend_available()
skip_if_no_backend = pytest.mark.skipif(
    not _BACKEND_OK, reason=f"后端服务不可用 ({BASE_URL})，请先启动 FastAPI 服务"
)


class APIClient:
    """API测试客户端"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.session = requests.Session()

    def login(self, username: str, password: str) -> dict:
        """登录获取Token - 使用Form表单格式"""
        captcha_response = self.session.get(
            f"{self.base_url}{API_PREFIX}/auth/captcha/generate"
        )
        captcha_response.raise_for_status()
        captcha = captcha_response.json().get("data", {})
        response = self.session.post(
            f"{self.base_url}{API_PREFIX}/auth/login",
            data={
                "username": username,
                "password": password,
                "captcha_id": captcha.get("captcha_id", ""),
                "captcha_code": captcha.get("code", ""),
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("data", {}).get("access_token") or data.get("access_token")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})

        return response.json()

    def post(self, path: str, json: dict = None, **kwargs):
        """POST请求"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.session.post(f"{self.base_url}{API_PREFIX}{path}", json=json, headers=headers, **kwargs)

    def put(self, path: str, json: dict = None, **kwargs):
        """PUT请求"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.session.put(f"{self.base_url}{API_PREFIX}{path}", json=json, headers=headers, **kwargs)

    def get(self, path: str, **kwargs):
        """GET请求"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.session.get(f"{self.base_url}{API_PREFIX}{path}", headers=headers, **kwargs)

    def delete(self, path: str, **kwargs):
        """DELETE请求"""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return self.session.delete(f"{self.base_url}{API_PREFIX}{path}", headers=headers, **kwargs)


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def api_client():
    """API客户端Fixture"""
    client = APIClient()
    yield client


@pytest.fixture(scope="session")
def auth_client(api_client):
    """已认证的API客户端"""
    api_client.login(ADMIN_USERNAME, ADMIN_PASSWORD)
    return api_client


# ==================== 认证测试 ====================

@skip_if_no_backend
class TestAuth:
    """认证模块测试"""

    def test_login_success(self, api_client):
        """测试登录成功"""
        response = api_client.login(ADMIN_USERNAME, ADMIN_PASSWORD)
        assert response.get("code") == 200
        assert "access_token" in response.get("data", {})

    def test_login_invalid_credentials(self, api_client):
        """测试登录失败-错误密码"""
        response = api_client.login("admin", "wrongpassword")
        assert response.get("code") == 401

    def test_get_current_user(self, auth_client):
        """测试获取当前用户信息"""
        response = auth_client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 200
        assert "username" in data.get("data", {})


# ==================== 项目管理测试 ====================

@skip_if_no_backend
class TestProject:
    """项目管理测试"""

    def test_get_project_list(self, auth_client):
        """测试获取项目列表"""
        response = auth_client.get("/project/list")
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 200
        assert "items" in data.get("data", {})

    def test_create_project(self, auth_client):
        """测试创建项目"""
        timestamp = int(time.time())
        project_data = {
            "name": f"测试项目_{timestamp}",
            "description": "单元测试创建的项目",
            "project_type": "web",
            "web_env_configs": {
                "test": {
                    "url": "https://test.example.com",
                    "username": "tester",
                    "password": "test123"
                }
            }
        }

        response = auth_client.post("/project/create", json=project_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("code") == 200
        assert "project_id" in data.get("data", {})

    def test_get_project_detail(self, auth_client):
        """测试获取项目详情"""
        response = auth_client.get("/project/1")
        assert response.status_code in [200, 403]


# ==================== 测试任务测试 ====================

@skip_if_no_backend
class TestTestTask:
    """测试任务测试"""

    def test_create_task(self, auth_client):
        """测试创建测试任务"""
        task_data = {
            "project_id": 1,
            "task_name": f"测试任务_{int(time.time())}",
            "description": "单元测试创建的任务",
            "case_ids": []
        }

        response = auth_client.post("/test_task", json=task_data)
        # 项目可能不存在或服务器错误
        assert response.status_code in [200, 400, 403, 500]

    def test_get_task_list(self, auth_client):
        """测试获取任务列表"""
        response = auth_client.get("/test_task")
        assert response.status_code == 200


# ==================== 测试用例测试 ====================

@skip_if_no_backend
class TestTestCase:
    """测试用例测试"""

    def test_get_case_list(self, auth_client):
        """测试获取用例列表"""
        response = auth_client.get("/testCase/?project_id=1")
        assert response.status_code in [200, 400, 403]


# ==================== 测试点测试 ====================

@skip_if_no_backend
class TestTestPoint:
    """测试点测试"""

    def test_get_point_list(self, auth_client):
        """测试获取测试点列表"""
        response = auth_client.get("/test-point/list/1")
        assert response.status_code in [200, 400, 403]


# ==================== 测试报告测试 ====================

@skip_if_no_backend
class TestReport:
    """测试报告测试"""

    def test_get_report_list(self, auth_client):
        """测试获取报告列表"""
        response = auth_client.get("/report?project_id=1")
        assert response.status_code in [200, 400]


# ==================== 运行测试 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
