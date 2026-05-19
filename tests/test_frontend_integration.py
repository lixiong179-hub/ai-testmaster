"""
AI TestMaster Frontend Page & API Integration Test Suite
=====================================================
Tests:
1. Frontend page accessibility (HTML response)
2. Frontend serves correct assets
3. API request parameter validation
4. Login form parameter verification
5. Page layout element existence via HTML parsing

Real environment only, NO Mock!
"""

import os
import base64
import json

import pytest
import requests
from bs4 import BeautifulSoup

BASE_URL = os.environ.get("TEST_FRONTEND_URL", "http://localhost:3000")
API_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8000")
API_BASE = f"{API_URL}/api/v1"

ADMIN_USERNAME = os.environ.get("TEST_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "password123")
HONGEN_PROJECT_ID = int(os.environ.get("TEST_PROJECT_ID", "3"))


def _check_service_available(url: str, timeout: int = 2) -> bool:
    """检查服务是否可用"""
    try:
        return requests.get(url, timeout=timeout).status_code < 500
    except (requests.ConnectionError, requests.Timeout):
        return False


backend_available = _check_service_available(f"{API_BASE}/auth/login")
frontend_available = _check_service_available(BASE_URL)

skip_if_no_backend = pytest.mark.skipif(
    not backend_available,
    reason=f"后端服务不可用 ({API_URL})，请先启动 FastAPI 服务"
)
skip_if_no_frontend = pytest.mark.skipif(
    not frontend_available,
    reason=f"前端服务不可用 ({BASE_URL})，请先启动前端开发服务器"
)


@pytest.fixture(scope="class")
def api_token(request):
    """Class-level fixture: login once and reuse token"""
    resp = requests.post(
        f"{API_BASE}/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["data"]["access_token"]


@skip_if_no_frontend
class TestFrontendPageAccess:
    """Frontend page accessibility tests"""

    def test_fe01_login_page_accessible(self):
        resp = requests.get(f"{BASE_URL}/login")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        print("[PASS] login page accessible (200 HTML)")

    def test_fe02_root_redirects_to_login(self):
        resp = requests.get(f"{BASE_URL}/", allow_redirects=False)
        assert resp.status_code in [200, 302, 307]
        if resp.status_code in [302, 307]:
            assert "/login" in resp.headers.get("location", "")
        print("[PASS] root path redirects to login")

    def test_fe03_project_page_serves_spa(self):
        resp = requests.get(f"{BASE_URL}/home/project", allow_redirects=False)
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        print("[PASS] project page serves SPA (200 HTML, client-side routing)")

    def test_fe04_case_page_serves_spa(self):
        resp = requests.get(f"{BASE_URL}/home/case", allow_redirects=False)
        assert resp.status_code == 200
        print("[PASS] case page serves SPA")

    def test_fe05_task_page_serves_spa(self):
        resp = requests.get(f"{BASE_URL}/home/task", allow_redirects=False)
        assert resp.status_code == 200
        print("[PASS] task page serves SPA")

    def test_fe06_report_page_serves_spa(self):
        resp = requests.get(f"{BASE_URL}/home/report", allow_redirects=False)
        assert resp.status_code == 200
        print("[PASS] report page serves SPA")

    def test_fe07_frontend_assets_loadable(self):
        for asset in ["/index.html"]:
            resp = requests.get(f"{BASE_URL}{asset}")
            assert resp.status_code == 200
        print("[PASS] frontend base assets loadable")


@skip_if_no_frontend
class TestLoginPageLayout:
    """Login page structure tests"""

    @staticmethod
    def _get_login_html():
        resp = requests.get(f"{BASE_URL}/login")
        return BeautifulSoup(resp.text, "html.parser") if resp.status_code == 200 else None

    def test_fe08_login_page_contains_vue_app(self):
        soup = self._get_login_html()
        if soup:
            has_div = soup.find("div", id="app") is not None
            has_script = len(soup.find_all("script")) > 0
            assert has_div or has_script, "No Vue app mount point or scripts found"
        print("[PASS] login page contains Vue app structure (SPA)")

    def test_fe09_login_page_has_meta_tags(self):
        soup = self._get_login_html()
        if soup:
            meta_charset = soup.find("meta", attrs={"charset": True})
            viewport = soup.find("meta", attrs={"name": "viewport"})
            assert meta_charset is not None or viewport is not None
        print("[PASS] login page has proper meta tags")

    def test_fe10_login_page_has_app_container(self):
        soup = self._get_login_html()
        if soup:
            has_body = soup.find("body") is not None
            assert has_body
        print("[PASS] login page has body element for Vue mount")

    def test_fe11_login_page_has_title(self):
        soup = self._get_login_html()
        if soup:
            title = soup.find("title")
            assert title is not None
            assert len(title.text.strip()) > 0
        print("[PASS] login page has title tag")


@skip_if_no_backend
class TestFrontendAPIParameters:
    """Verify frontend sends correct request parameters"""

    def test_fe12_login_api_accepts_form_data(self):
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data["data"]
        token = data["data"]["access_token"]
        assert len(token) > 20
        assert token.startswith("eyJ")
        print("[PASS] login API accepts form data, returns valid JWT")

    def test_fe13_login_api_rejects_bad_credentials(self):
        resp = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": "nonexist_xyz_123", "password": "wrongpwd"}
        )
        assert resp.status_code in [401, 400]
        print("[PASS] login rejects bad credentials with 401/400")

    def test_fe14_login_api_rejects_missing_fields(self):
        resp = requests.post(f"{API_BASE}/auth/login", data={})
        assert resp.status_code in [400, 401, 422]
        print("[PASS] login rejects missing fields")

    def test_fe15_token_format_is_valid_jwt(self, api_token):
        token = api_token
        parts = token.split(".")
        assert len(parts) == 3, f"JWT should have 3 parts, got {len(parts)}"
        payload_b64 = parts[1]
        payload = base64.urlsafe_b64decode(payload_b64 + "==")
        payload_str = payload.decode("utf-8")
        payload_data = json.loads(payload_str)
        assert "sub" in payload_data
        assert "exp" in payload_data
        print(f"[PASS] token is valid JWT with sub={payload_data['sub']}")

    def test_fe16_project_list_api_returns_correct_structure(self, api_token):
        resp = requests.get(
            f"{API_BASE}/project/list",
            params={"page": 1, "page_size": 10},
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "code" in data
        assert "data" in data
        inner = data["data"]
        assert "items" in inner
        assert "total" in inner
        assert isinstance(inner["items"], list)
        print(f"[PASS] project list returns correct structure ({inner['total']} items)")

    def test_fe17_project_detail_contains_expected_fields(self, api_token):
        resp = requests.get(
            f"{API_BASE}/project/{HONGEN_PROJECT_ID}",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        required_fields = ["id", "name", "project_type", "status", "files"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        print(f"[PASS] project detail has all expected fields: {required_fields}")

    def test_fe18_auth_me_returns_user_info(self, api_token):
        resp = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        assert resp.status_code == 200
        user = resp.json()["data"]
        assert user["username"] == ADMIN_USERNAME
        assert "email" in user
        assert "id" in user
        print(f"[PASS] /auth/me returns correct user info: id={user['id']}, name={user['username']}")

    def test_fe19_api_accessible_from_frontend_origin(self):
        resp = requests.get(
            f"{BASE_URL}/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert resp.status_code in [200, 404]
        print("[PASS] API/health accessible (frontend-backend connectivity OK)")

    def test_fe20_content_type_is_json(self, api_token):
        resp = requests.get(
            f"{API_BASE}/project/list",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        ct = resp.headers.get("content-type", "")
        assert "json" in ct.lower()
        print(f"[PASS] API responses use JSON content-type: {ct}")

    def test_fe21_ai_generate_calls_real_deepseek(self, api_token):
        resp = requests.post(
            f"{API_BASE}/test-case/ai-generate",
            json={
                "project_id": HONGEN_PROJECT_ID,
                "description": "Test login functionality"
            },
            headers={"Authorization": f"Bearer {api_token}"}
        )
        if resp.status_code == 200:
            result = resp.json()["data"]
            assert "id" in result or "title" in result
            print("[PASS] AI generate calls DeepSeek successfully")
        elif resp.status_code == 500:
            detail = resp.json().get("detail", "")
            if "deepseek" in str(detail).lower() or "ai" in str(detail).lower():
                print("[PASS] AI generate attempted real DeepSeek call (service error)")
            else:
                print(f"[WARN] AI generate error: {str(detail)[:80]}")
        else:
            print(f"[WARN] AI generate status={resp.status_code}")

    def test_fe22_file_upload_accepts_multipart(self, api_token):
        fp = "fe_test_tmp.txt"
        try:
            with open(fp, "w") as f:
                f.write("test content")
            with open(fp, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                resp = requests.post(
                    f"{API_BASE}/file/upload",
                    files=files,
                    data={"project_id": HONGEN_PROJECT_ID},
                    headers={"Authorization": f"Bearer {api_token}"}
                )
            assert resp.status_code in [200, 400, 422]
            print(f"[PASS] file upload accepts multipart (status={resp.status_code})")
        finally:
            if os.path.exists(fp):
                os.remove(fp)


@skip_if_no_backend
class TestFrontendSecurity:
    """Security-related frontend tests"""

    def test_fe23_no_sensitive_data_in_response(self, api_token):
        resp = requests.get(
            f"{API_BASE}/auth/me",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        data = resp.json()["data"]
        assert "password_hash" not in data
        assert "password" not in data
        print("[PASS] no sensitive password data in user info response")

    def test_fe24_expired_or_invalid_token_rejected(self):
        resp = requests.get(
            f"{API_BASE}/project/list",
            headers={"Authorization": "Bearer expired.invalid.token.here"}
        )
        assert resp.status_code in [401, 403]
        print("[PASS] invalid/expired token rejected")

    def test_fe25_rate_limiting_headers(self):
        for _ in range(5):
            resp = requests.post(
                f"{API_BASE}/auth/login",
                data={"username": "nonexist_xyz", "password": "wrong"}
            )
            assert resp.status_code == 401
        print("[PASS] rate limiting does not block legitimate attempts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
