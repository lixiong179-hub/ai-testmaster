import pytest
from app.services.precondition.utils import solve_captcha_math
from app.services.precondition.models import (
    TestObjectType,
    TestObjectInfo,
    LoginFormInfo,
    MobileLoginFormInfo,
    MobileAppConfig,
    PreconditionTimingConfig,
    PreconditionConfigError,
    PreconditionError,
    LoginError,
)


class TestSolveCaptchaMath:
    def test_addition(self):
        assert solve_captcha_math("3 + 5 = ?") == "8"

    def test_subtraction(self):
        assert solve_captcha_math("10 - 3 = ?") == "7"

    def test_multiplication(self):
        assert solve_captcha_math("4 × 2 = ?") == "8"

    def test_division(self):
        assert solve_captcha_math("10 ÷ 2 = ?") == "5"

    def test_star_multiplication(self):
        assert solve_captcha_math("3 * 4") == "12"

    def test_slash_division(self):
        assert solve_captcha_math("9 / 3") == "3"

    def test_division_by_zero(self):
        result = solve_captcha_math("5 ÷ 0")
        assert result == "5"

    def test_single_number(self):
        result = solve_captcha_math("1234")
        assert result == "1234"

    def test_empty_string(self):
        assert solve_captcha_math("") == ""

    def test_chinese_plus(self):
        assert solve_captcha_math("3＋5") == "8"

    def test_chinese_minus(self):
        assert solve_captcha_math("10－3") == "7"

    def test_fallback_alphanumeric(self):
        result = solve_captcha_math("abc123")
        assert result is not None

    def test_captcha_keyword_filtered(self):
        result = solve_captcha_math("captcha: 42")
        assert "42" in result


class TestTestObjectInfo:
    def test_validate_web_success(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url="https://example.com")
        info.validate_web()

    def test_validate_web_no_url(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url=None)
        with pytest.raises(PreconditionConfigError, match="URL"):
            info.validate_web()

    def test_validate_web_invalid_url(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url="ftp://example.com")
        with pytest.raises(PreconditionConfigError, match="URL格式"):
            info.validate_web()

    def test_validate_app_success(self):
        info = TestObjectInfo(
            type=TestObjectType.APP, device_id="device1", app_package="com.example",
        )
        info.validate_app()

    def test_validate_app_no_device(self):
        info = TestObjectInfo(type=TestObjectType.APP, device_id=None, app_package="com.example")
        with pytest.raises(PreconditionConfigError, match="设备ID"):
            info.validate_app()

    def test_validate_app_no_package(self):
        info = TestObjectInfo(type=TestObjectType.APP, device_id="device1", app_package=None)
        with pytest.raises(PreconditionConfigError, match="App包名"):
            info.validate_app()


class TestLoginFormInfo:
    def test_is_complete(self):
        form = LoginFormInfo(
            username_input={"x": 1}, password_input={"x": 2}, submit_button={"x": 3},
        )
        assert form.is_complete() is True

    def test_not_complete(self):
        form = LoginFormInfo(username_input={"x": 1})
        assert form.is_complete() is False

    def test_has_captcha(self):
        form = LoginFormInfo(captcha_input={"x": 1}, captcha_image={"x": 2})
        assert form.has_captcha() is True

    def test_no_captcha(self):
        form = LoginFormInfo()
        assert form.has_captcha() is False


class TestMobileLoginFormInfo:
    def test_is_complete_account_login(self):
        form = MobileLoginFormInfo(
            username_input={"x": 1}, password_input={"x": 2}, submit_button={"x": 3},
        )
        assert form.is_complete() is True

    def test_is_complete_phone_login(self):
        form = MobileLoginFormInfo(
            phone_input={"x": 1}, sms_code_input={"x": 2}, submit_button={"x": 3},
        )
        assert form.is_complete() is True

    def test_not_complete(self):
        form = MobileLoginFormInfo()
        assert form.is_complete() is False


class TestMobileAppConfig:
    def test_defaults(self):
        config = MobileAppConfig()
        assert config.platform_name == "Android"
        assert config.no_reset is False
        assert config.new_command_timeout == 300


class TestPreconditionTimingConfig:
    def test_defaults(self):
        config = PreconditionTimingConfig()
        assert config.max_login_wait_time == 10
        assert config.wait_interval == 1


class TestExceptionHierarchy:
    def test_precondition_error(self):
        with pytest.raises(PreconditionError):
            raise PreconditionError("test")

    def test_config_error_inherits(self):
        with pytest.raises(PreconditionError):
            raise PreconditionConfigError("test")

    def test_login_error_inherits(self):
        with pytest.raises(PreconditionError):
            raise LoginError("test")
