
"""前置条件数据模型 - 定义前置条件体系所需的数据类和枚举。"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class TestObjectType(str, Enum):
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
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    device_id: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None

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
    username_input: Optional[Dict[str, Any]] = None
    password_input: Optional[Dict[str, Any]] = None
    submit_button: Optional[Dict[str, Any]] = None
    captcha_input: Optional[Dict[str, Any]] = None
    captcha_image: Optional[Dict[str, Any]] = None

    def is_complete(self) -> bool:
        return all([
            self.username_input is not None,
            self.password_input is not None,
            self.submit_button is not None
        ])

    def has_captcha(self) -> bool:
        return self.captcha_input is not None and self.captcha_image is not None


@dataclass
class MobileLoginFormInfo:
    """移动端登录表单信息。"""
    username_input: Optional[Dict[str, Any]] = None
    password_input: Optional[Dict[str, Any]] = None
    submit_button: Optional[Dict[str, Any]] = None
    captcha_input: Optional[Dict[str, Any]] = None
    captcha_image: Optional[Dict[str, Any]] = None
    agree_checkbox: Optional[Dict[str, Any]] = None
    phone_input: Optional[Dict[str, Any]] = None
    sms_code_input: Optional[Dict[str, Any]] = None
    get_sms_code_button: Optional[Dict[str, Any]] = None

    def is_complete(self) -> bool:
        has_account_login = all([
            self.username_input is not None,
            self.password_input is not None,
            self.submit_button is not None
        ])
        has_phone_login = all([
            self.phone_input is not None,
            self.sms_code_input is not None,
            self.submit_button is not None
        ])
        return has_account_login or has_phone_login


@dataclass
class MobileAppConfig:
    """移动端App配置。"""
    platform_name: str = "Android"
    device_name: Optional[str] = None
    udid: Optional[str] = None
    platform_version: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None
    bundle_id: Optional[str] = None
    app_path: Optional[str] = None
    automation_name: Optional[str] = None
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
