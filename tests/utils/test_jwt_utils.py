"""JWT工具单元测试 - jwt_utils"""
import pytest
from datetime import timedelta
from app.utils.jwt_utils import (
    create_access_token, create_refresh_token, decode_token,
    verify_access_token, verify_refresh_token, refresh_access_token,
    verify_password, get_password_hash, _utcnow,
)
from app.core.exception import AuthenticationError
from datetime import datetime


class TestUtcnow:
    def test_returns_naive_datetime(self):
        result = _utcnow()
        assert isinstance(result, datetime)
        assert result.tzinfo is None

    def test_returns_recent_time(self):
        result = _utcnow()
        diff = abs((datetime.utcnow() - result).total_seconds())
        assert diff < 2


class TestCreateAccessToken:
    def test_create_and_decode(self):
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_custom_expiry(self):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))
        payload = decode_token(token)
        assert payload["sub"] == "1"


class TestCreateRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token({"sub": "1"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"

    def test_custom_expiry(self):
        token = create_refresh_token({"sub": "1"}, expires_delta=timedelta(days=1))
        payload = decode_token(token)
        assert payload["type"] == "refresh"


class TestDecodeToken:
    def test_invalid_token(self):
        with pytest.raises(AuthenticationError):
            decode_token("invalid.token.string")


class TestVerifyAccessToken:
    def test_valid_access_token(self):
        token = create_access_token({"sub": "1"})
        payload = verify_access_token(token)
        assert payload["type"] == "access"

    def test_refresh_token_rejected(self):
        token = create_refresh_token({"sub": "1"})
        with pytest.raises(AuthenticationError, match="access"):
            verify_access_token(token)


class TestVerifyRefreshToken:
    def test_valid_refresh_token(self):
        token = create_refresh_token({"sub": "1"})
        payload = verify_refresh_token(token)
        assert payload["type"] == "refresh"

    def test_access_token_rejected(self):
        token = create_access_token({"sub": "1"})
        with pytest.raises(AuthenticationError, match="refresh"):
            verify_refresh_token(token)


class TestRefreshAccessToken:
    def test_refresh_success(self):
        refresh = create_refresh_token({"sub": "42"})
        new_access = refresh_access_token(refresh)
        payload = verify_access_token(new_access)
        assert payload["sub"] == "42"

    def test_refresh_with_invalid_token(self):
        with pytest.raises(AuthenticationError):
            refresh_access_token("invalid.token")


class TestPasswordFunctions:
    def test_verify_password_correct(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_wrong(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("wrong", hashed) is False

    def test_get_password_hash_differs(self):
        assert get_password_hash("test") != "test"
