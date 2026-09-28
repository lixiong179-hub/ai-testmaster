"""OIDC 服务异常类型（从 oidc_service.py 拆出，避免 mixin 循环导入）。

异常层级：
    OIDCServiceError（基类）
        ├── OIDCDisabledError   OIDC 功能未启用（503）
        ├── OIDCConfigError     IdP 配置异常（400）
        ├── OIDCStateError      state 校验失败（400，CSRF 攻击嫌疑）
        ├── OIDCTokenError      id_token / access_token 校验异常（401）
        └── OIDCUserNotBoundError 用户未绑定且不允许自动注册（403）
"""
from typing import Optional

from app.core.exception._base import BaseAPIException


class OIDCServiceError(BaseAPIException):
    """OIDC 服务异常基类。"""

    def __init__(self, msg: str, code: int = 400, details: Optional[dict] = None) -> None:
        super().__init__(msg=msg, code=code, details=details)


class OIDCDisabledError(OIDCServiceError):
    """OIDC 功能未启用异常。"""

    def __init__(self) -> None:
        super().__init__(msg="OIDC SSO 未启用", code=503)


class OIDCConfigError(OIDCServiceError):
    """OIDC IdP 配置异常。"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg, code=400)


class OIDCStateError(OIDCServiceError):
    """OIDC state 校验异常（CSRF 攻击嫌疑）。"""

    def __init__(self, msg: str = "OIDC state 校验失败") -> None:
        super().__init__(msg=msg, code=400)


class OIDCTokenError(OIDCServiceError):
    """OIDC id_token / access_token 校验异常。"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg, code=401)


class OIDCUserNotBoundError(OIDCServiceError):
    """OIDC 用户未绑定本地账号且不允许自动注册。"""

    def __init__(self, msg: str = "用户未绑定本地账号，请联系管理员开通") -> None:
        super().__init__(msg=msg, code=403)


__all__ = [
    "OIDCServiceError",
    "OIDCDisabledError",
    "OIDCConfigError",
    "OIDCStateError",
    "OIDCTokenError",
    "OIDCUserNotBoundError",
]
