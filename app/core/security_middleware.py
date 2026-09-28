"""Phase 3 安全合规中间件（Task 13）：CSRF/HSTS/CSP 防护。

设计目的：
    将 HSTS、CSP、CSRF 三类安全防护从 main.py 的 SecurityHeadersMiddleware
    中分离，避免 main.py 膨胀。SecurityHeadersMiddleware 仅保留通用响应头，
    本模块专注 Web 安全防护三件套。

组件：
    - SecurityHeadersMiddleware : 通用安全响应头（X-Content-Type-Options 等）
    - HSTSMiddleware            : Strict-Transport-Security，仅生产环境启用
    - CSPMiddleware             : Content-Security-Policy，限制资源加载来源
    - CSRFMiddleware            : 跨站请求伪造防护（Origin/Referer + 双提交 Cookie）

设计原则：
    - 配置驱动：所有策略通过 settings 控制，支持环境变量覆盖
    - 渐进启用：开发环境默认关闭 HSTS（http 会被浏览器拒绝）
    - 异常容忍：CSRF 校验失败返回 403，不阻断已认证的 API 请求（JWT 模式低风险）
"""
from __future__ import annotations

import hmac
import secrets
from typing import Optional

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class HSTSMiddleware(BaseHTTPMiddleware):
    """HSTS 中间件 — 注入 Strict-Transport-Security 响应头。

    业务用途：强制浏览器后续请求走 HTTPS，防 SSL Strip 降级攻击。
    边界场景：开发环境（ENVIRONMENT != prod）不注入，避免 http 下浏览器锁定。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        # 仅生产环境注入 HSTS，开发环境 http 会导致浏览器拒绝访问
        if settings.SECURITY_HSTS_ENABLED and settings.ENVIRONMENT == "prod":
            hsts_value = settings.hsts_header_value
            if hsts_value:
                response.headers["Strict-Transport-Security"] = hsts_value
        return response


class CSPMiddleware(BaseHTTPMiddleware):
    """CSP 中间件 — 注入 Content-Security-Policy 响应头。

    业务用途：限制页面资源加载来源，防 XSS/数据注入/点击劫持。
    设计要点：frame-ancestors 'none' 等效 X-Frame-Options: DENY，防点击劫持。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if settings.SECURITY_CSP_ENABLED:
            response.headers["Content-Security-Policy"] = settings.SECURITY_CSP_POLICY
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 防护中间件 — Origin/Referer 校验 + 双提交 Cookie 模式。

    业务背景：
        本平台 JWT 通过 Authorization 头传递，CSRF 风险低。但若调用方
        改用 Cookie 模式（如服务端渲染场景），则需 CSRF 防护。

    校验流程（仅对非安全方法生效）：
        1. 安全方法（GET/HEAD/OPTIONS）直接放行
        2. 携带 Authorization 头的请求视为 JWT 模式，直接放行
        3. 无 Authorization 头时走双提交 Cookie 校验：
           - 从 Cookie 读取 csrf_token
           - 从请求头读取 X-CSRF-Token
           - 两者必须存在且一致（hmac.compare_digest 防时序攻击）
        4. Cookie 无 csrf_token 时回退到 Origin/Referer 校验：
           - Origin 必须在 CORS 白名单内
           - 无 Origin 时校验 Referer

    属性：
        _allowed_origins: CORS 白名单集合，O(1) 查询
    """

    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        # 预计算 CORS 白名单集合，避免每次请求解析
        self._allowed_origins: set[str] = set(settings.cors_origins_list)
        # CORS_ORIGINS='*' 时 CSRF Origin 校验放行所有源（与 CORS 行为一致）
        self._allow_all_origins: bool = "*" in self._allowed_origins

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.SECURITY_CSRF_ENABLED:
            return await call_next(request)

        method = request.method.upper()
        # 安全方法豁免（RFC 7231：不应产生副作用）
        if method in settings.csrf_exempt_methods_list:
            return await call_next(request)

        # 路径豁免：SAML ACS 等 IdP 回调端点已通过 RelayState 实现 CSRF 防护
        if request.url.path in settings.csrf_exempt_paths_list:
            return await call_next(request)

        # JWT 模式（Authorization 头存在）直接放行
        if "authorization" in {k.lower() for k in request.headers.keys()}:
            return await call_next(request)

        # 双提交 Cookie 模式校验
        cookie_token = request.cookies.get(settings.SECURITY_CSRF_COOKIE_NAME)
        header_token = request.headers.get(settings.SECURITY_CSRF_TOKEN_HEADER)

        if cookie_token and header_token:
            if hmac.compare_digest(cookie_token, header_token):
                return await call_next(request)
            logger.warning(
                f"[CSRF] 双提交 Cookie 校验失败: path={request.url.path} method={method}"
            )
            return _csrf_rejected("CSRF token 不匹配")

        # 无 CSRF token 时回退到 Origin/Referer 校验
        if cookie_token is None:
            origin_check = self._check_origin_or_referer(request)
            if origin_check:
                return await call_next(request)
            logger.warning(
                f"[CSRF] Origin/Referer 校验失败: path={request.url.path} method={method}"
            )
            return _csrf_rejected("缺少 CSRF token 且 Origin/Referer 校验失败")

        # cookie_token 存在但 header_token 缺失
        logger.warning(
            f"[CSRF] 请求头缺少 {settings.SECURITY_CSRF_TOKEN_HEADER}: "
            f"path={request.url.path} method={method}"
        )
        return _csrf_rejected("请求头缺少 CSRF token")

    def _check_origin_or_referer(self, request: Request) -> bool:
        """校验 Origin 或 Referer 是否在 CORS 白名单内。

        Args:
            request: Starlette 请求对象

        Returns:
            bool: True 表示校验通过

        边界场景：
            - CORS_ORIGINS='*' 时放行所有源（与 CORS 行为一致，仅开发/测试环境）
            - 生产环境 CORS_ORIGINS 为显式白名单，此处严格匹配
        """
        # CORS 配置为通配符时放行所有源（开发/测试环境）
        if self._allow_all_origins:
            return True

        origin = request.headers.get("origin")
        if origin:
            return origin in self._allowed_origins

        referer = request.headers.get("referer")
        if referer:
            # 从 Referer 提取 origin（scheme://host[:port]）
            try:
                from urllib.parse import urlparse

                parsed = urlparse(referer)
                referer_origin = f"{parsed.scheme}://{parsed.netloc}"
                return referer_origin in self._allowed_origins
            except Exception:
                return False
        return False


def _csrf_rejected(detail: str) -> JSONResponse:
    """构造 CSRF 校验失败的 403 响应。"""
    return JSONResponse(
        status_code=403,
        content={"code": 403, "msg": detail, "data": None},
    )


def generate_csrf_token() -> str:
    """生成 CSRF token（32 字节随机串，URL-safe base64 编码）。

    业务用途：登录成功后由前端调用 /api/v1/auth/csrf-token 获取，
    前端写入 Cookie（SameSite=Strict）并在后续请求头携带。
    """
    return secrets.token_urlsafe(32)


__all__ = [
    "CSPMiddleware",
    "CSRFMiddleware",
    "HSTSMiddleware",
    "generate_csrf_token",
]
