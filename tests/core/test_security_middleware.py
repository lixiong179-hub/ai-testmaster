"""Phase 3 Task 13: CSRF/HSTS/CSP 防护中间件单元测试。

覆盖：
    - HSTSMiddleware: 生产环境注入 / 开发环境跳过 / 配置禁用
    - CSPMiddleware: 注入 Content-Security-Policy / 配置禁用
    - CSRFMiddleware: 安全方法豁免 / JWT 模式放行 / 双提交 Cookie / Origin 校验 / Referer 回退
    - generate_csrf_token: 长度 / 唯一性
    - config.hsts_header_value: 构造正确性
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.security_middleware import (
    CSPMiddleware,
    CSRFMiddleware,
    HSTSMiddleware,
    generate_csrf_token,
)


# ── 测试用基础应用工厂 ──


def _create_test_app(middleware_cls, **middleware_kwargs) -> FastAPI:
    """创建挂载指定中间件的测试应用。"""
    app = FastAPI()

    @app.get("/")
    async def root():
        return JSONResponse({"ok": True})

    @app.head("/")
    async def head_root():
        return JSONResponse({"ok": True})

    @app.post("/")
    async def post_root():
        return JSONResponse({"ok": True})

    app.add_middleware(middleware_cls, **middleware_kwargs)
    return app


# ── HSTSMiddleware 测试 ──


class TestHSTSMiddleware:
    """HSTS 中间件测试。"""

    def test_hsts_not_injected_in_dev_environment(self) -> None:
        """开发环境不注入 HSTS 头。"""
        app = _create_test_app(HSTSMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert resp.status_code == 200
        # 默认 ENVIRONMENT != "prod"，不注入 HSTS
        assert "strict-transport-security" not in resp.headers

    def test_hsts_injected_in_prod_environment(self, monkeypatch) -> None:
        """生产环境注入 HSTS 头。"""
        monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
        monkeypatch.setattr(settings, "SECURITY_HSTS_ENABLED", True)
        app = _create_test_app(HSTSMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert resp.status_code == 200
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_hsts_disabled_by_config(self, monkeypatch) -> None:
        """配置禁用时即使生产环境也不注入。"""
        monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
        monkeypatch.setattr(settings, "SECURITY_HSTS_ENABLED", False)
        app = _create_test_app(HSTSMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert "strict-transport-security" not in resp.headers

    def test_hsts_preload_flag(self, monkeypatch) -> None:
        """启用 preload 时包含 preload 指令。"""
        monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
        monkeypatch.setattr(settings, "SECURITY_HSTS_PRELOAD", True)
        app = _create_test_app(HSTSMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        hsts = resp.headers.get("strict-transport-security", "")
        assert "preload" in hsts


# ── CSPMiddleware 测试 ──


class TestCSPMiddleware:
    """CSP 中间件测试。"""

    def test_csp_header_injected(self) -> None:
        """启用时注入 Content-Security-Policy 头。"""
        app = _create_test_app(CSPMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert resp.status_code == 200
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_csp_disabled_by_config(self, monkeypatch) -> None:
        """配置禁用时不注入 CSP 头。"""
        monkeypatch.setattr(settings, "SECURITY_CSP_ENABLED", False)
        app = _create_test_app(CSPMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert "content-security-policy" not in resp.headers


# ── CSRFMiddleware 测试 ──


class TestCSRFMiddleware:
    """CSRF 中间件测试。"""

    @pytest.fixture(autouse=True)
    def _enforce_cors_whitelist(self, monkeypatch):
        """强制使用显式 CORS 白名单（非通配符 *），确保 CSRF Origin 校验生效。

        业务背景：.env 中 CORS_ORIGINS=* 会导致 _allow_all_origins=True，
        CSRF Origin 校验放行所有源，使拒绝场景测试失效。
        """

        monkeypatch.setattr(
            settings, "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        )

    def test_safe_method_exempt(self) -> None:
        """GET 请求（安全方法）直接放行。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.get("/")
        assert resp.status_code == 200

    def test_post_without_auth_or_csrf_rejected(self) -> None:
        """POST 请求无 Authorization 和 CSRF token 时被拒绝。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post("/")
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["msg"] or "Origin" in resp.json()["msg"]

    def test_post_with_jwt_authorization_passes(self) -> None:
        """POST 请求携带 Authorization 头（JWT 模式）直接放行。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post(
                "/",
                headers={"Authorization": "Bearer fake.jwt.token"},
            )
        assert resp.status_code == 200

    def test_post_with_valid_csrf_double_submit_passes(self) -> None:
        """POST 请求携带匹配的 Cookie + Header CSRF token 时放行。"""
        app = _create_test_app(CSRFMiddleware)
        token = generate_csrf_token()
        with TestClient(app) as client:
            resp = client.post(
                "/",
                cookies={settings.SECURITY_CSRF_COOKIE_NAME: token},
                headers={settings.SECURITY_CSRF_TOKEN_HEADER: token},
            )
        assert resp.status_code == 200

    def test_post_with_mismatched_csrf_token_rejected(self) -> None:
        """POST 请求 Cookie 与 Header 的 CSRF token 不匹配时被拒绝。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post(
                "/",
                cookies={settings.SECURITY_CSRF_COOKIE_NAME: "token_a"},
                headers={settings.SECURITY_CSRF_TOKEN_HEADER: "token_b"},
            )
        assert resp.status_code == 403
        assert "不匹配" in resp.json()["msg"]

    def test_post_with_cookie_but_no_header_rejected(self) -> None:
        """POST 请求有 Cookie token 但缺少 Header token 时被拒绝。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post(
                "/",
                cookies={settings.SECURITY_CSRF_COOKIE_NAME: "token_a"},
            )
        assert resp.status_code == 403
        assert "缺少" in resp.json()["msg"]

    def test_post_with_valid_origin_passes(self) -> None:
        """POST 请求无 CSRF token 但 Origin 在白名单时放行。"""
        app = _create_test_app(CSRFMiddleware)
        # 使用配置中的第一个允许源
        allowed_origin = settings.cors_origins_list[0]
        with TestClient(app) as client:
            resp = client.post(
                "/",
                headers={"Origin": allowed_origin},
            )
        assert resp.status_code == 200

    def test_post_with_invalid_origin_rejected(self) -> None:
        """POST 请求无 CSRF token 且 Origin 不在白名单时被拒绝。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post(
                "/",
                headers={"Origin": "https://evil.example.com"},
            )
        assert resp.status_code == 403

    def test_post_with_valid_referer_passes(self, monkeypatch) -> None:
        """POST 请求无 Origin 但 Referer 在白名单时放行（直接测试 _check_origin_or_referer）。"""
        from starlette.requests import Request

        # 使用有效的 origin 而非测试环境的 "*"
        test_origin = "http://localhost:5173"
        monkeypatch.setattr(settings, "CORS_ORIGINS", test_origin)
        app = _create_test_app(CSRFMiddleware)
        middleware = CSRFMiddleware(app)

        # 构造仅含 Referer 头的模拟请求
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"referer", f"{test_origin}/some/path".encode())],
            "path": "/",
            "query_string": b"",
        }
        request = Request(scope)
        assert middleware._check_origin_or_referer(request) is True

    def test_post_with_invalid_referer_rejected(self, monkeypatch) -> None:
        """POST 请求 Referer 不在白名单时校验失败。"""
        from starlette.requests import Request

        test_origin = "http://localhost:5173"
        monkeypatch.setattr(settings, "CORS_ORIGINS", test_origin)
        app = _create_test_app(CSRFMiddleware)
        middleware = CSRFMiddleware(app)

        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"referer", b"https://evil.example.com/path")],
            "path": "/",
            "query_string": b"",
        }
        request = Request(scope)
        assert middleware._check_origin_or_referer(request) is False

    def test_post_without_origin_or_referer_rejected(self) -> None:
        """POST 请求无 Origin 和 Referer 时校验失败。"""
        from starlette.requests import Request

        app = _create_test_app(CSRFMiddleware)
        middleware = CSRFMiddleware(app)

        scope = {
            "type": "http",
            "method": "POST",
            "headers": [],
            "path": "/",
            "query_string": b"",
        }
        request = Request(scope)
        assert middleware._check_origin_or_referer(request) is False

    def test_csrf_disabled_by_config(self, monkeypatch) -> None:
        """配置禁用时所有请求放行。"""
        monkeypatch.setattr(settings, "SECURITY_CSRF_ENABLED", False)
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.post("/")
        assert resp.status_code == 200

    def test_head_method_exempt(self) -> None:
        """HEAD 请求（安全方法）放行。"""
        app = _create_test_app(CSRFMiddleware)
        with TestClient(app) as client:
            resp = client.head("/")
        assert resp.status_code == 200


# ── generate_csrf_token 测试 ──


class TestGenerateCsrfToken:
    """CSRF token 生成函数测试。"""

    def test_token_is_string(self) -> None:
        """生成的 token 是字符串。"""
        token = generate_csrf_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_uniqueness(self) -> None:
        """连续生成的 token 不同。"""
        tokens = {generate_csrf_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_token_min_length(self) -> None:
        """token 长度 >= 32（32 字节 base64 编码后约 43 字符）。"""
        token = generate_csrf_token()
        assert len(token) >= 32


# ── config 属性测试 ──


class TestConfigHstsHeaderValue:
    """config.hsts_header_value 属性测试。"""

    def test_hsts_value_with_defaults(self) -> None:
        """默认配置包含 max-age 和 includeSubDomains。"""
        value = settings.hsts_header_value
        # SECURITY_HSTS_ENABLED 默认 True
        if settings.SECURITY_HSTS_ENABLED:
            assert "max-age=" in value
            assert "includeSubDomains" in value

    def test_hsts_value_when_disabled(self, monkeypatch) -> None:
        """禁用时返回空字符串。"""
        monkeypatch.setattr(settings, "SECURITY_HSTS_ENABLED", False)
        assert settings.hsts_header_value == ""

    def test_hsts_value_without_subdomains(self, monkeypatch) -> None:
        """禁用 includeSubDomains 时不包含该指令。"""
        monkeypatch.setattr(settings, "SECURITY_HSTS_ENABLED", True)
        monkeypatch.setattr(settings, "SECURITY_HSTS_INCLUDE_SUBDOMAINS", False)
        value = settings.hsts_header_value
        assert "includeSubDomains" not in value

    def test_csrf_exempt_methods_list(self) -> None:
        """csrf_exempt_methods_list 返回大写方法列表。"""
        methods = settings.csrf_exempt_methods_list
        assert "GET" in methods
        assert "HEAD" in methods
        assert "OPTIONS" in methods
