"""Precondition Parser - 兼容代理模块

所有实现已迁移到 precondition/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.precondition import (
    TestObjectType,
    PreconditionError,
    PreconditionConfigError,
    LoginError,
    TestObjectInfo,
    LoginFormInfo,
    MobileLoginFormInfo,
    MobileAppConfig,
    PreconditionTimingConfig,
    handle_precondition_errors,
    solve_captcha_math,
    recognize_login_form,
)

__all__ = [
    "TestObjectType",
    "PreconditionError",
    "PreconditionConfigError",
    "LoginError",
    "TestObjectInfo",
    "LoginFormInfo",
    "MobileLoginFormInfo",
    "MobileAppConfig",
    "PreconditionTimingConfig",
    "handle_precondition_errors",
    "solve_captcha_math",
    "recognize_login_form",
]
