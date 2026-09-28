"""Phase 3 Task 5: OIDC SSO 适配 API 端点。

端点概览：
    - GET  /auth/oidc/providers       : 列出所有已配置的 IdP（无需认证）
    - GET  /auth/oidc/login           : 跳转到 IdP 授权页（302 重定向）
    - GET  /auth/oidc/callback        : OIDC 回调处理（换 token + 用户映射 + 签发本平台 token）
    - GET  /auth/oidc/metadata        : 获取单个 IdP 元数据（无需认证）

设计要点：
    - OIDC_SSO_ENABLED=False 时所有端点返回 503
    - /login 接受 provider + redirect_to 参数，生成 state 后 302 跳转 IdP
    - /callback 校验 state + code，完成登录后返回 JSON（含 access_token）
    - 所有端点无需 CSRF 校验（已通过 state 实现 CSRF 防护）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exception._base import create_response
from app.db.database import async_get_db
from app.schemas.common import ApiResponse
from app.services.oidc_service import (
    OIDCConfigError,
    OIDCDisabledError,
    OIDCService,
    OIDCServiceError,
    OIDCStateError,
    OIDCTokenError,
    OIDCUserNotBoundError,
    get_oidc_service,
)

router = APIRouter()


def _oidc_service_or_503() -> OIDCService:
    """获取 OIDCService 实例，未启用时抛 503。"""
    try:
        return get_oidc_service()
    except OIDCDisabledError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=e.msg) from e
    except OIDCConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e


@router.get(
    "/oidc/providers",
    response_model=ApiResponse,
    summary="列出已配置的 OIDC IdP",
    description="返回所有已配置的 IdP 列表与默认 IdP 标识，供前端渲染登录入口。",
)
async def list_oidc_providers() -> dict:
    """列出所有已配置的 OIDC IdP。"""
    service = _oidc_service_or_503()
    metadata = service.get_provider_metadata()
    return create_response(data=metadata)


@router.get(
    "/oidc/metadata",
    response_model=ApiResponse,
    summary="获取单个 OIDC IdP 元数据",
    description="返回指定 IdP 的元数据（issuer/client_id/scopes/redirect_uri），脱敏隐藏 client_secret。",
)
async def get_oidc_metadata(
    provider: Optional[str] = Query(None, description="IdP 标识；不传返回所有 IdP 列表"),
) -> dict:
    """获取单个或全部 IdP 元数据。"""
    service = _oidc_service_or_503()
    try:
        metadata = service.get_provider_metadata(provider)
        return create_response(data=metadata)
    except OIDCConfigError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.msg) from e


@router.get(
    "/oidc/login",
    summary="OIDC 登录 — 跳转到 IdP 授权页",
    description="生成 state 与 nonce 后 302 重定向到 IdP 授权端点。IdP 登录完成后回调 /auth/oidc/callback。",
)
async def oidc_login(
    provider: Optional[str] = Query(None, description="IdP 标识；不传使用 OIDC_DEFAULT_PROVIDER"),
    redirect_to: Optional[str] = Query(
        None, description="登录成功后前端跳转目标路径（如 /dashboard），存入 state 上下文"
    ),
) -> RedirectResponse:
    """跳转到 IdP 授权页（302 重定向）。"""
    service = _oidc_service_or_503()
    try:
        auth_url, _state = service.build_authorization_url(provider=provider, redirect_to=redirect_to)
        logger.info(f"OIDC 登录跳转: provider={provider or settings.OIDC_DEFAULT_PROVIDER}")
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except OIDCConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except OIDCServiceError as e:
        logger.error(f"OIDC 登录跳转失败: {e.msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.msg) from e


@router.get(
    "/oidc/callback",
    response_model=ApiResponse,
    summary="OIDC 回调 — 换取 token 并签发本平台 JWT",
    description="IdP 授权后回调此端点，校验 state 与 code，完成用户映射后返回本平台 access_token/refresh_token。",
)
async def oidc_callback(
    code: Optional[str] = Query(None, description="IdP 返回的授权码"),
    state: Optional[str] = Query(None, description="授权请求时发送的 state，用于 CSRF 防护"),
    error: Optional[str] = Query(None, description="IdP 返回的错误码（如 access_denied）"),
    error_description: Optional[str] = Query(None, description="IdP 返回的错误描述"),
    provider: Optional[str] = Query(
        None, description="IdP 标识；若 IdP 未在 state 中回传 provider，需调用方显式传入"
    ),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """处理 OIDC 回调。"""
    # IdP 返回错误（用户拒绝授权等）
    if error:
        logger.warning(
            f"OIDC 回调收到 IdP 错误: error={error} description={error_description}"
        )
        return create_response(
            data={"error": error, "error_description": error_description or ""},
            msg=f"IdP 拒绝授权: {error}",
            code=status.HTTP_400_BAD_REQUEST,
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 code 或 state 参数",
        )

    service = _oidc_service_or_503()

    # 若调用方未显式传入 provider，使用默认 IdP
    actual_provider = provider or service.resolve_provider(None)

    try:
        result = await service.handle_callback(
            db=db,
            provider=actual_provider,
            code=code,
            state=state,
        )
        logger.info(
            f"OIDC 回调成功: provider={actual_provider} user_id={result['user']['id']}"
        )
        return create_response(data=result, msg="OIDC 登录成功")
    except OIDCStateError as e:
        logger.warning(f"OIDC state 校验失败: {e.msg}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except OIDCTokenError as e:
        logger.error(f"OIDC token 校验失败: {e.msg}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.msg) from e
    except OIDCUserNotBoundError as e:
        logger.warning(f"OIDC 用户未绑定: {e.msg}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.msg) from e
    except OIDCConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except OIDCServiceError as e:
        logger.error(f"OIDC 回调失败: {e.msg}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.msg) from e
