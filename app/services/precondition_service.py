"""Precondition Service - 向后兼容代理模块

所有实现已迁移到 precondition/ 子包，统一从 app.services.precondition 导入。
本文件保留以兼容现有引用，将在后续版本中移除。
"""
from app.services.precondition import (
    PreconditionService,
    create_precondition_service,
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
    "PreconditionService",
    "create_precondition_service",
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
