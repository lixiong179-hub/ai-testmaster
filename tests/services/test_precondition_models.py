import pytest
from app.services.precondition.models import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    LoginError,
    TestObjectInfo,
    LoginFormInfo,
    MobileLoginFormInfo,
    MobileAppConfig,
    PreconditionTimingConfig,
)


class TestTestObjectType:
    def test_web_value(self):
        assert TestObjectType.WEB.value == "web"

    def test_app_value(self):
        assert TestObjectType.APP.value == "app"


class TestPreconditionErrors:
    def test_base_error(self):
        with pytest.raises(PreconditionError):
            raise PreconditionError("test")

    def test_config_error_inherits(self):
        with pytest.raises(PreconditionError):
            raise PreconditionConfigError("config error")

    def test_login_error_inherits(self):
        with pytest.raises(PreconditionError):
            raise LoginError("login error")


class TestTestObjectInfo:
    def test_web_validation_success(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url="https://example.com")
        info.validate_web()

    def test_web_validation_no_url(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url=None)
        with pytest.raises(PreconditionConfigError, match="URL"):
            info.validate_web()

    def test_web_validation_invalid_url(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url="ftp://example.com")
        with pytest.raises(PreconditionConfigError, match="URL格式"):
            info.validate_web()

    def test_web_validation_http(self):
        info = TestObjectInfo(type=TestObjectType.WEB, url="http://example.com")
        info.validate_web()

    def test_app_validation_success(self):
        info = TestObjectInfo(
            type=TestObjectType.APP,
            device_id="device1",
            app_package="com.example.app",
        )
        info.validate_app()

    def test_app_validation_no_device(self):
        info = TestObjectInfo(type=TestObjectType.APP, device_id=None, app_package="com.example")
        with pytest.raises(PreconditionConfigError, match="设备ID"):
            info.validate_app()

    def test_app_validation_no_package(self):
        info = TestObjectInfo(type=TestObjectType.APP, device_id="device1", app_package=None)
        with pytest.raises(PreconditionConfigError, match="App包名"):
            info.validate_app()


class TestLoginFormInfo:
    def test_is_complete_true(self):
        info = LoginFormInfo(
            username_input={"x": 1},
            password_input={"x": 2},
            submit_button={"x": 3},
        )
        assert info.is_complete() is True

    def test_is_complete_false(self):
        info = LoginFormInfo()
        assert info.is_complete() is False

    def test_is_complete_partial(self):
        info = LoginFormInfo(username_input={"x": 1})
        assert info.is_complete() is False

    def test_has_captcha_true(self):
        info = LoginFormInfo(captcha_input={"x": 1}, captcha_image={"x": 2})
        assert info.has_captcha() is True

    def test_has_captcha_false(self):
        info = LoginFormInfo(captcha_input={"x": 1})
        assert info.has_captcha() is False

    def test_has_captcha_none(self):
        info = LoginFormInfo()
        assert info.has_captcha() is False


class TestMobileLoginFormInfo:
    def test_is_complete_account_login(self):
        info = MobileLoginFormInfo(
            username_input={"x": 1},
            password_input={"x": 2},
            submit_button={"x": 3},
        )
        assert info.is_complete() is True

    def test_is_complete_phone_login(self):
        info = MobileLoginFormInfo(
            phone_input={"x": 1},
            sms_code_input={"x": 2},
            submit_button={"x": 3},
        )
        assert info.is_complete() is True

    def test_is_complete_false(self):
        info = MobileLoginFormInfo()
        assert info.is_complete() is False


class TestMobileAppConfig:
    def test_defaults(self):
        config = MobileAppConfig()
        assert config.platform_name == "Android"
        assert config.no_reset is False
        assert config.new_command_timeout == 300

    def test_custom_values(self):
        config = MobileAppConfig(
            device_name="Pixel",
            udid="abc123",
            app_package="com.test.app",
        )
        assert config.device_name == "Pixel"
        assert config.udid == "abc123"


class TestPreconditionTimingConfig:
    def test_defaults(self):
        config = PreconditionTimingConfig()
        assert config.max_login_wait_time == 10
        assert config.wait_interval == 1
        assert config.click_delay == 0.2
