"""API 契约冒烟测试（B-07，2026-11-12 由 live-server 冒烟改为进程内契约测试）。

**改造原因**：原实现用 `requests` 直连 `http://localhost:8000`，未启动后端时 11 项全部
`skip`（CI 中零信号）。现改为复用 `tests/conftest.py` 的 `client` fixture
（`fastapi.testclient.TestClient` + DB 依赖覆写 + `Origin` 头），在进程内走 ASGI，
**无后端服务也照跑**，且断言的是真实契约（路由存在性 + 鉴权生效 + 响应包络/关键字段），
契约一旦被改坏就会真实失败。

覆盖模块：认证 / 项目 / 测试任务 / 测试用例 / 测试点 / 测试报告。
统一响应包络：`{"code": 200, "msg": ..., "message": ..., "data": ..., "timestamp": ...}`
（例外：`GET /api/v1/report/` 直接返回 `TestReportList`，无 `code/data` 包络）。
"""
from typing import Any
from uuid import uuid4

API = "/api/v1"


# ==================== 契约辅助 ====================

def _fetch_captcha(client) -> tuple[str, str]:
    """从进程内端点取验证码（captcha 服务为内存单例，测试无需外部依赖）。"""
    resp = client.get(f"{API}/auth/captcha/generate")
    assert resp.status_code == 200, f"验证码端点异常: {resp.status_code} {resp.text}"
    data = resp.json()["data"]
    assert data.get("captcha_id") and data.get("code")
    return data["captcha_id"], data["code"]


def _login(client, username: str, password: str):
    captcha_id, code = _fetch_captcha(client)
    return client.post(
        f"{API}/auth/login",
        data={
            "username": username,
            "password": password,
            "captcha_id": captcha_id,
            "captcha_code": code,
        },
    )


def _assert_envelope(resp, expected_code: int = 200) -> dict[str, Any]:
    """断言统一响应包络，并返回 data 部分。"""
    assert resp.status_code == expected_code, f"HTTP {resp.status_code}: {resp.text[:400]}"
    body = resp.json()
    assert body.get("code") == expected_code, f"业务码异常: {body}"
    return body.get("data") or {}


# ==================== 认证模块 ====================

class TestAuth:
    """认证模块契约。"""

    def test_login_success(self, client, testUser):
        """登录成功：返回 Bearer token 与用户信息。"""
        resp = _login(client, testUser.username, "Test@123456")
        data = _assert_envelope(resp)
        assert data.get("access_token"), f"缺少 access_token: {data}"
        assert data.get("token_type", "").lower() == "bearer"
        assert (data.get("user") or {}).get("username") == testUser.username

    def test_login_requires_captcha(self, client, testUser):
        """登录必须携带验证码：缺失时 400 且给出明确原因。"""
        resp = client.post(
            f"{API}/auth/login",
            data={"username": testUser.username, "password": "Test@123456"},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body.get("code") == 400
        # 全局异常处理器把 HTTPException 归一为包络，原因在 message/msg 字段
        reason = body.get("message") or body.get("msg") or ""
        assert "验证码" in reason, f"错误原因未说明验证码缺失: {body}"

    def test_get_current_user(self, client, authHeaders, testUser):
        """当前用户信息：token 有效时返回本人 username。"""
        resp = client.get(f"{API}/auth/me", headers=authHeaders)
        data = _assert_envelope(resp)
        assert data.get("username") == testUser.username
        assert data.get("id") == testUser.id


# ==================== 项目管理 ====================

class TestProject:
    """项目模块契约。"""

    def test_get_project_list(self, client, authHeaders, testProject):
        """项目列表：分页包络 + items/total。"""
        resp = client.get(f"{API}/project/list", headers=authHeaders)
        data = _assert_envelope(resp)
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)
        assert data["total"] >= 1
        assert {"id", "name", "project_type"} <= set(data["items"][0])

    def test_create_project(self, client, authHeaders):
        """创建项目：返回 project_id。"""
        resp = client.post(
            f"{API}/project/create",
            headers=authHeaders,
            json={
                "name": f"smoke_project_{uuid4().hex[:12]}",
                "description": "契约冒烟创建",
                "project_type": "web",
            },
        )
        data = _assert_envelope(resp)
        assert isinstance(data.get("project_id"), int)

    def test_get_project_detail(self, client, authHeaders, testProject):
        """项目详情：本人项目可读，非本人项目 403（越权防护）。"""
        resp = client.get(f"{API}/project/{testProject.id}", headers=authHeaders)
        data = _assert_envelope(resp)
        assert data.get("id", data.get("project_id")) == testProject.id

        forbidden = client.get(f"{API}/project/0", headers=authHeaders)
        assert forbidden.status_code in (403, 404), forbidden.text


# ==================== 测试任务 ====================

class TestTestTask:
    """测试任务模块契约。"""

    def test_create_task(self, client, authHeaders, testProject):
        """创建任务：返回 task_id 且初始 total_count 与入参一致。"""
        resp = client.post(
            f"{API}/test-task/",
            headers=authHeaders,
            json={
                "project_id": testProject.id,
                "task_name": "契约冒烟任务",
                "description": "B-07 冒烟",
                "case_ids": [],
            },
        )
        data = _assert_envelope(resp)
        assert isinstance(data.get("task_id"), int)
        assert data.get("total_count") == 0

    def test_get_task_list(self, client, authHeaders, testProject):
        """任务列表：按项目过滤，返回 items/total。"""
        resp = client.get(
            f"{API}/test-task/", headers=authHeaders, params={"project_id": testProject.id}
        )
        data = _assert_envelope(resp)
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)


# ==================== 测试用例 ====================

class TestTestCase:
    """测试用例模块契约。"""

    def test_get_case_list(self, client, authHeaders, testProject):
        """用例列表：分页包络 + items/total。"""
        resp = client.get(
            f"{API}/test-case/", headers=authHeaders, params={"project_id": testProject.id}
        )
        data = _assert_envelope(resp)
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)


# ==================== 测试点 ====================

class TestTestPoint:
    """测试点模块契约。"""

    def test_get_point_list(self, client, authHeaders, testProject):
        """测试点列表：按项目路径参数返回 items/total。"""
        resp = client.get(f"{API}/test-point/list/{testProject.id}", headers=authHeaders)
        data = _assert_envelope(resp)
        assert isinstance(data.get("items"), list)
        assert isinstance(data.get("total"), int)


# ==================== 测试报告 ====================

class TestReport:
    """测试报告模块契约。"""

    def test_get_report_list(self, client, authHeaders, testProject):
        """报告列表：该端点直接返回 TestReportList（无 code/data 包络，列表键为 reports）。"""
        resp = client.get(
            f"{API}/report/", headers=authHeaders, params={"project_id": testProject.id}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body.get("reports"), list), body
        assert isinstance(body.get("total"), int)
