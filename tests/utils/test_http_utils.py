import base64
import pytest
from app.utils.http_utils import build_auth_headers


class TestBuildAuthHeadersBasic:
    def test_returns_base_headers_without_auth(self):
        headers = build_auth_headers("none", {})
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Authorization" not in headers

    def test_unknown_auth_type_returns_base_headers(self):
        headers = build_auth_headers("unknown_type", {})
        assert "Authorization" not in headers
        assert "Cookie" not in headers


class TestBuildAuthHeadersBasicAuth:
    def test_basic_auth_with_valid_credentials(self):
        headers = build_auth_headers("basic", {"username": "admin", "password": "secret"})
        assert "Authorization" in headers
        expected = base64.b64encode(b"admin:secret").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_basic_auth_missing_username(self):
        headers = build_auth_headers("basic", {"password": "secret"})
        assert "Authorization" not in headers

    def test_basic_auth_missing_password(self):
        headers = build_auth_headers("basic", {"username": "admin"})
        assert "Authorization" not in headers

    def test_basic_auth_empty_credentials(self):
        headers = build_auth_headers("basic", {"username": "", "password": ""})
        assert "Authorization" not in headers

    def test_basic_auth_empty_config(self):
        headers = build_auth_headers("basic", {})
        assert "Authorization" not in headers


class TestBuildAuthHeadersBearer:
    def test_bearer_with_valid_token(self):
        headers = build_auth_headers("bearer", {"token": "mytoken123"})
        assert headers["Authorization"] == "Bearer mytoken123"

    def test_bearer_with_empty_token(self):
        headers = build_auth_headers("bearer", {"token": ""})
        assert "Authorization" not in headers

    def test_bearer_missing_token_key(self):
        headers = build_auth_headers("bearer", {})
        assert "Authorization" not in headers


class TestBuildAuthHeadersApiKey:
    def test_api_key_with_default_header(self):
        headers = build_auth_headers("api_key", {"api_key": "key123"})
        assert headers["X-API-Key"] == "key123"

    def test_api_key_with_custom_header(self):
        headers = build_auth_headers("api_key", {"api_key": "key123", "api_key_header": "X-Custom-Key"})
        assert headers["X-Custom-Key"] == "key123"
        assert "X-API-Key" not in headers

    def test_api_key_empty_value(self):
        headers = build_auth_headers("api_key", {"api_key": ""})
        assert "X-API-Key" not in headers

    def test_api_key_missing_key(self):
        headers = build_auth_headers("api_key", {})
        assert "X-API-Key" not in headers


class TestBuildAuthHeadersCookie:
    def test_cookie_with_value(self):
        headers = build_auth_headers("cookie", {"cookie": "session=abc123"})
        assert headers["Cookie"] == "session=abc123"

    def test_cookie_empty_value(self):
        headers = build_auth_headers("cookie", {"cookie": ""})
        assert "Cookie" not in headers

    def test_cookie_missing_key(self):
        headers = build_auth_headers("cookie", {})
        assert "Cookie" not in headers


class TestBuildAuthHeadersEdgeCases:
    def test_base_headers_always_present(self):
        for auth_type in ("basic", "bearer", "api_key", "cookie", "none", "other"):
            headers = build_auth_headers(auth_type, {})
            assert "User-Agent" in headers
            assert "Accept" in headers
            assert "Accept-Language" in headers

    def test_basic_auth_special_characters(self):
        headers = build_auth_headers("basic", {"username": "user@domain", "password": "p@ss:w0rd!"})
        assert "Authorization" in headers
        expected = base64.b64encode(b"user@domain:p@ss:w0rd!").decode()
        assert headers["Authorization"] == f"Basic {expected}"

    def test_bearer_token_with_special_chars(self):
        headers = build_auth_headers("bearer", {"token": "eyJhbGciOiJIUzI1NiJ9.test.sig"})
        assert headers["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.test.sig"
