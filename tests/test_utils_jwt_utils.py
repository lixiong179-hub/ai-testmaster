import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_access_token,
    verify_refresh_token,
    refresh_access_token,
    verify_password,
    get_password_hash,
    _utcnow,
)
from app.core.exception import AuthenticationError


class TestUtcnow:
    def test_returns_naive_datetime_for_mysql_compat(self):
        result = _utcnow()
        assert result.tzinfo is None

    def test_returns_recent_time(self):
        before = datetime.utcnow()
        result = _utcnow()
        after = datetime.utcnow()
        assert before <= result <= after


class TestCreateAccessToken:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user1"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self):
        token = create_access_token({"sub": "user1"}, expires_delta=timedelta(minutes=5))
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "access"

    def test_create_access_token_default_expiry(self):
        token = create_access_token({"sub": "user1"})
        payload = decode_token(token)
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_contains_data(self):
        token = create_access_token({"sub": "user1", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["role"] == "admin"


class TestCreateRefreshToken:
    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "user1"})
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user1"

    def test_create_refresh_token_with_custom_expiry(self):
        token = create_refresh_token({"sub": "user1"}, expires_delta=timedelta(days=1))
        payload = decode_token(token)
        assert payload["type"] == "refresh"


class TestDecodeToken:
    def test_decode_valid_token(self):
        token = create_access_token({"sub": "user1"})
        payload = decode_token(token)
        assert payload["sub"] == "user1"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(AuthenticationError, match="Token无效"):
            decode_token("invalid.token.string")

    def test_decode_expired_token_raises(self):
        token = create_access_token({"sub": "user1"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(AuthenticationError, match="Token无效"):
            decode_token(token)

    def test_decode_tampered_token_raises(self):
        token = create_access_token({"sub": "user1"})
        tampered = token[:-5] + "xxxxx"
        with pytest.raises(AuthenticationError, match="Token无效"):
            decode_token(tampered)


class TestVerifyAccessToken:
    def test_verify_valid_access_token(self):
        token = create_access_token({"sub": "user1"})
        payload = verify_access_token(token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "access"

    def test_verify_refresh_token_as_access_raises(self):
        token = create_refresh_token({"sub": "user1"})
        with pytest.raises(AuthenticationError, match="access token"):
            verify_access_token(token)

    def test_verify_invalid_token_raises(self):
        with pytest.raises(AuthenticationError):
            verify_access_token("invalid")


class TestVerifyRefreshToken:
    def test_verify_valid_refresh_token(self):
        token = create_refresh_token({"sub": "user1"})
        payload = verify_refresh_token(token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "refresh"

    def test_verify_access_token_as_refresh_raises(self):
        token = create_access_token({"sub": "user1"})
        with pytest.raises(AuthenticationError, match="refresh token"):
            verify_refresh_token(token)


class TestRefreshAccessToken:
    def test_refresh_access_token(self):
        refresh_token = create_refresh_token({"sub": "user1"})
        new_access_token = refresh_access_token(refresh_token)
        payload = verify_access_token(new_access_token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "access"

    def test_refresh_with_invalid_token_raises(self):
        with pytest.raises(AuthenticationError):
            refresh_access_token("invalid_token")

    def test_refresh_with_access_token_raises(self):
        access_token = create_access_token({"sub": "user1"})
        with pytest.raises(AuthenticationError, match="refresh token"):
            refresh_access_token(access_token)

    def test_refresh_token_missing_sub_raises(self):
        refresh_token = create_refresh_token({"role": "admin"})
        with pytest.raises(AuthenticationError, match="缺少sub"):
            refresh_access_token(refresh_token)


class TestPasswordHash:
    def test_hash_and_verify(self):
        hashed = get_password_hash("mypassword")
        assert hashed != "mypassword"
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password_fails(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = get_password_hash("same")
        h2 = get_password_hash("same")
        assert h1 != h2

    def test_empty_password(self):
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
