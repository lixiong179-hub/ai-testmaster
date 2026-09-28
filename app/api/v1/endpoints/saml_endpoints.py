"""Phase 3 Task 4: SAML 2.0 SSO SP API 端点。

端点概览：
    - GET  /auth/saml/providers       : 列出所有已配置的 IdP（无需认证）
    - GET  /auth/saml/metadata        : 返回 SP 元数据 XML（供 IdP 导入）
    - GET  /auth/saml/login           : 跳转到 IdP SSO 页（302 重定向）
    - POST /auth/saml/acs             : ACS 回调（IdP POST SAMLResponse 到此）
    - GET  /auth/saml/slo             : SLO 回调（IdP GET LogoutResponse 到此）

设计要点：
    - SAML_SSO_ENABLED=False 时所有端点返回 503
    - /login 接受 provider + redirect_to 参数，生成 RelayState 后 302 跳转 IdP
    - /acs 接收 IdP POST 的 SAMLResponse，校验后返回 JSON（含 access_token）
    - /metadata 返回 application/xml 格式的 SP 元数据
    - 所有端点无需 CSRF 校验（已通过 RelayState 实现 CSRF 防护）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exception._base import create_response
from app.db.database import async_get_db
from app.schemas.common import ApiResponse
from app.services.saml_service import (
    SAMLConfigError,
    SAMLDisabledError,
    SAMLRelayStateError,
    SAMLResponseError,
    SAMLService,
    SAMLServiceError,
    SAMLUserNotBoundError,
    get_saml_service,
)

router = APIRouter()


def _saml_service_or_503() -> SAMLService:
    """获取 SAMLService 实例，未启用时抛 503。"""
    try:
        return get_saml_service()
    except SAMLDisabledError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=e.msg
        ) from e
    except SAMLConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e


@router.get(
    "/saml/providers",
    response_model=ApiResponse,
    summary="列出已配置的 SAML IdP",
    description="返回所有已配置的 IdP 列表与默认 IdP 标识，供前端渲染登录入口。",
)
async def list_saml_providers() -> dict:
    """列出所有已配置的 SAML IdP。"""
    service = _saml_service_or_503()
    metadata = service.get_provider_metadata()
    return create_response(data=metadata)


@router.get(
    "/saml/metadata",
    summary="获取 SP 元数据 XML",
    description="返回 SP 元数据 XML（EntityDescriptor），供 IdP 管理员导入以配置 SP 信任关系。",
    responses={200: {"content": {"application/xml": {}}}},
)
async def get_saml_metadata(
    provider: Optional[str] = Query(None, description="IdP 标识；不传使用默认 IdP"),
) -> Response:
    """返回 SP 元数据 XML。"""
    service = _saml_service_or_503()
    try:
        xml = service.generate_sp_metadata(provider)
        return Response(content=xml, media_type="application/xml")
    except SAMLConfigError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.msg) from e


@router.get(
    "/saml/login",
    summary="SAML 登录 — 跳转到 IdP SSO 页",
    description="生成 AuthnRequest 与 RelayState 后 302 重定向到 IdP SSO 端点。"
    "IdP 登录完成后 POST SAMLResponse 到 /auth/saml/acs。",
)
async def saml_login(
    request: Request,
    provider: Optional[str] = Query(None, description="IdP 标识；不传使用 SAML_DEFAULT_PROVIDER"),
    redirect_to: Optional[str] = Query(
        None, description="登录成功后前端跳转目标路径（如 /dashboard），存入 RelayState 上下文"
    ),
) -> RedirectResponse:
    """跳转到 IdP SSO 页（302 重定向）。"""
    service = _saml_service_or_503()
    request_data = SAMLService.build_request_data_from_request(request)
    try:
        auth_url, _relay_state = service.build_login_redirect(
            provider=provider, redirect_to=redirect_to, request_data=request_data
        )
        logger.info(
            f"SAML 登录跳转: provider={provider or settings.SAML_DEFAULT_PROVIDER}"
        )
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    except SAMLConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except SAMLServiceError as e:
        logger.error(f"SAML 登录跳转失败: {e.msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.msg
        ) from e


@router.post(
    "/saml/acs",
    response_model=ApiResponse,
    summary="SAML ACS — 断言消费服务",
    description="IdP POST SAMLResponse 到此端点，校验 RelayState 与 SAMLResponse 后，"
    "完成用户映射并签发本平台 access_token/refresh_token。",
)
async def saml_acs(
    request: Request,
    SAMLResponse: str = Form(..., description="IdP POST 的 Base64 编码 SAMLResponse"),
    RelayState: str = Form(..., description="登录请求时发送的 RelayState，用于 CSRF 防护"),
    provider: Optional[str] = Query(
        None, description="IdP 标识；若未在 RelayState 中存储，需调用方显式传入"
    ),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """处理 SAML ACS 回调。"""
    service = _saml_service_or_503()
    request_data = SAMLService.build_request_data_from_request(
        request, saml_response=SAMLResponse
    )
    # provider 优先从查询参数获取，否则从 RelayState 上下文恢复
    actual_provider = provider or service.resolve_provider(None)
    try:
        result = await service.handle_acs(
            db=db,
            provider=actual_provider,
            saml_response=SAMLResponse,
            relay_state=RelayState,
            request_data=request_data,
        )
        logger.info(
            f"SAML ACS 回调成功: provider={actual_provider} user_id={result['user']['id']}"
        )
        return create_response(data=result, msg="SAML 登录成功")
    except SAMLRelayStateError as e:
        logger.warning(f"SAML RelayState 校验失败: {e.msg}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except SAMLResponseError as e:
        logger.error(f"SAML SAMLResponse 校验失败: {e.msg}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=e.msg
        ) from e
    except SAMLUserNotBoundError as e:
        logger.warning(f"SAML 用户未绑定: {e.msg}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.msg) from e
    except SAMLConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except SAMLServiceError as e:
        logger.error(f"SAML ACS 回调失败: {e.msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.msg
        ) from e


@router.get(
    "/saml/slo",
    response_model=ApiResponse,
    summary="SAML SLO — 单点登出回调",
    description="IdP GET LogoutResponse 到此端点，校验后注销本地会话。",
)
async def saml_slo(
    request: Request,
    provider: Optional[str] = Query(None, description="IdP 标识"),
) -> dict:
    """处理 SAML SLO 回调。"""
    service = _saml_service_or_503()
    request_data = SAMLService.build_request_data_from_request(request)
    actual_provider = provider or service.resolve_provider(None)
    try:
        success, message = service.handle_slo(
            provider=actual_provider, request_data=request_data
        )
        if success:
            return create_response(data={"logged_out": True}, msg=message)
        return create_response(
            data={"logged_out": False}, msg=message, code=status.HTTP_400_BAD_REQUEST
        )
    except SAMLConfigError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.msg) from e
    except SAMLServiceError as e:
        logger.error(f"SAML SLO 回调失败: {e.msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.msg
        ) from e
