"""前置条件数据模型 - 定义前置条件体系所需的数据类和枚举。"""

from typing import Any
from dataclasses import dataclass
from enum import StrEnum


class TestObjectType(StrEnum):
    """被测对象类型枚举。"""

    WEB = "web"
    APP = "app"


class PreconditionError(Exception):
    """前置条件基础异常。"""

    pass


class PreconditionConfigError(PreconditionError):
    """前置条件配置错误。"""

    pass


class LoginError(PreconditionError):
    """登录错误。"""

    pass


@dataclass
class TestObjectInfo:
    """被测对象信息。"""

    type: TestObjectType
    url: str | None = None
    username: str | None = None
    password: str | None = None
    device_id: str | None = None
    app_package: str | None = None
    app_activity: str | None = None

    def validate_web(self) -> None:
        if not self.url:
            raise PreconditionConfigError("Web项目必须配置访问地址(URL)")
        if not self.url.startswith(("http://", "https://")):
            raise PreconditionConfigError(f"无效的URL格式: {self.url}")

    def validate_app(self) -> None:
        if not self.device_id:
            raise PreconditionConfigError("App项目必须配置设备ID")
        if not self.app_package:
            raise PreconditionConfigError("App项目必须配置App包名")


@dataclass
class LoginFormInfo:
    """Web登录表单信息。"""

    username_input: dict[str, Any] | None = None
    password_input: dict[str, Any] | None = None
    submit_button: dict[str, Any] | None = None
    captcha_input: dict[str, Any] | None = None
    captcha_image: dict[str, Any] | None = None

    def is_complete(self) -> bool:
        return all([self.username_input is not None, self.password_input is not None, self.submit_button is not None])

    def has_captcha(self) -> bool:
        return self.captcha_input is not None and self.captcha_image is not None


@dataclass
class MobileLoginFormInfo:
    """移动端登录表单信息。"""

    username_input: dict[str, Any] | None = None
    password_input: dict[str, Any] | None = None
    submit_button: dict[str, Any] | None = None
    captcha_input: dict[str, Any] | None = None
    captcha_image: dict[str, Any] | None = None
    agree_checkbox: dict[str, Any] | None = None
    phone_input: dict[str, Any] | None = None
    sms_code_input: dict[str, Any] | None = None
    get_sms_code_button: dict[str, Any] | None = None

    def is_complete(self) -> bool:
        has_account_login = all(
            [self.username_input is not None, self.password_input is not None, self.submit_button is not None]
        )
        has_phone_login = all(
            [self.phone_input is not None, self.sms_code_input is not None, self.submit_button is not None]
        )
        return has_account_login or has_phone_login


@dataclass
class MobileAppConfig:
    """移动端App配置。"""

    platform_name: str = "Android"
    device_name: str | None = None
    udid: str | None = None
    platform_version: str | None = None
    app_package: str | None = None
    app_activity: str | None = None
    bundle_id: str | None = None
    app_path: str | None = None
    automation_name: str | None = None
    no_reset: bool = False
    full_reset: bool = False
    new_command_timeout: int = 300
    implicit_wait: int = 10


@dataclass
class PreconditionTimingConfig:
    """前置条件时序配置。"""

    max_login_wait_time: int = 10
    wait_interval: int = 1
    captcha_padding: int = 10
    input_delay: int = 10
    click_delay: float = 0.2
    fill_delay: float = 0.1
    mobile_login_wait: int = 2
