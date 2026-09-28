"""SAML 2.0 协议操作封装。

封装 python3-saml 的核心协议操作，提供统一的接口供 SAMLService 调用：
    - generate_sp_metadata_xml: 生成 SP 元数据 XML（供 IdP 配置导入）
    - build_authn_request_redirect: 生成 AuthnRequest 并构造 HTTP-Redirect 跳转 URL
    - parse_saml_response: 解析并验证 IdP 返回的 SAMLResponse，提取 NameID/属性/SessionIndex
    - build_logout_request_redirect: 生成 LogoutRequest 并构造 HTTP-Redirect 跳转 URL
    - parse_logout_response: 解析 LogoutResponse，判断 SLO 是否成功

设计要点：
    - 所有函数接收 request_data dict（python3-saml 要求的请求上下文格式）
    - strict 模式从 IdP 配置继承，测试时可传 strict=False 放宽校验
    - 延迟导入 onelogin.saml2 避免模块加载时强依赖 xmlsec1
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from loguru import logger

from app.services.saml._settings_builder import build_full_settings_dict


def _build_auth(request_data: Dict[str, Any], settings_dict: Dict[str, Any]) -> Any:
    """构造 OneLogin_Saml2_Auth 实例（延迟导入）。

    Args:
        request_data: python3-saml 请求上下文（含 https/http_host/script_name/get_data/post_data）
        settings_dict: 完整的 Settings 字典

    Returns:
        OneLogin_Saml2_Auth 实例
    """
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    return OneLogin_Saml2_Auth(request_data, old_settings=settings_dict)


def _build_settings(settings_dict: Dict[str, Any]) -> Any:
    """构造 OneLogin_Saml2_Settings 实例（延迟导入）。

    Args:
        settings_dict: 完整的 Settings 字典

    Returns:
        OneLogin_Saml2_Settings 实例
    """
    from onelogin.saml2.settings import OneLogin_Saml2_Settings
    return OneLogin_Saml2_Settings(settings_dict, sp_validation_only=True)


def generate_sp_metadata_xml(idp_cfg: Dict[str, Any], *, strict: bool = True) -> str:
    """生成 SP 元数据 XML。

    SP 元数据描述本服务的 EntityID / ACS URL / SLO URL / 证书，
    供 IdP 管理员导入以配置 SP 信任关系。

    Args:
        idp_cfg: IdP 配置字典（用于继承 strict / security 配置）
        strict: 是否启用严格模式

    Returns:
        str: SP 元数据 XML 字符串
    """
    settings_dict = build_full_settings_dict(idp_cfg, strict=strict)
    saml_settings = _build_settings(settings_dict)
    metadata = saml_settings.get_sp_metadata()
    # 校验元数据完整性（errors 为空表示有效）
    errors = saml_settings.validate_metadata(metadata)
    if errors:
        logger.warning(f"SAML SP 元数据校验警告: {errors}")
    return metadata


def build_authn_request_redirect(
    request_data: Dict[str, Any],
    idp_cfg: Dict[str, Any],
    relay_state: str,
    *,
    strict: bool = True,
) -> str:
    """生成 AuthnRequest 并构造 HTTP-Redirect 跳转 URL。

    SP 发起 SSO 时，生成 AuthnRequest XML，签名后编码为查询参数，
    构造 IdP SSO URL + SAMLRequest + RelayState 的完整跳转 URL。

    Args:
        request_data: python3-saml 请求上下文
        idp_cfg: IdP 配置字典
        relay_state: RelayState 值（用于 CSRF 防护与请求上下文保持）
        strict: 是否启用严格模式

    Returns:
        str: 完整的 IdP 跳转 URL（含 SAMLRequest + RelayState + SigAlgorithm + Signature）
    """
    settings_dict = build_full_settings_dict(idp_cfg, strict=strict)
    auth = _build_auth(request_data, settings_dict)
    return auth.login(return_to=relay_state)


def parse_saml_response(
    request_data: Dict[str, Any],
    idp_cfg: Dict[str, Any],
    *,
    strict: bool = True,
) -> Dict[str, Any]:
    """解析并验证 IdP 返回的 SAMLResponse。

    IdP POST SAMLResponse 到 ACS URL 后，本函数：
        1. 调用 auth.process_response() 解析 XML 并验证签名/时间/受众
        2. 检查 errors（签名失败/过期/受众不匹配等）
        3. 提取 NameID / 属性 / SessionIndex / Issuer

    Args:
        request_data: python3-saml 请求上下文（post_data 需含 SAMLResponse）
        idp_cfg: IdP 配置字典
        strict: 是否启用严格模式

    Returns:
        dict: 含 nameid / nameid_format / session_index / issuer / attributes / nameid_value

    Raises:
        ValueError: SAMLResponse 解析或校验失败
    """
    settings_dict = build_full_settings_dict(idp_cfg, strict=strict)
    auth = _build_auth(request_data, settings_dict)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        error_reason = auth.get_last_error_reason()
        msg = f"SAMLResponse 校验失败: errors={errors} reason={error_reason}"
        logger.error(msg)
        raise ValueError(msg)

    if not auth.is_authenticated():
        msg = "SAMLResponse 校验通过但用户未认证（可能断言不包含 AuthnStatement）"
        logger.warning(msg)
        raise ValueError(msg)

    nameid = auth.get_nameid()
    nameid_format = auth.get_nameid_format()
    session_index = auth.get_session_index()
    issuer = auth.get_issuers()[0] if auth.get_issuers() else ""
    attributes = auth.get_attributes() or {}
    # 属性值统一为列表，此处转为单值（取第一个）便于上层使用
    flat_attrs: Dict[str, Any] = {}
    for k, v in attributes.items():
        flat_attrs[k] = v[0] if isinstance(v, list) and v else v

    return {
        "nameid": nameid,
        "nameid_format": nameid_format,
        "session_index": session_index,
        "issuer": issuer,
        "attributes": flat_attrs,
    }


def build_logout_request_redirect(
    request_data: Dict[str, Any],
    idp_cfg: Dict[str, Any],
    name_id: str,
    session_index: str,
    relay_state: str = "",
    *,
    strict: bool = True,
) -> str:
    """生成 LogoutRequest 并构造 HTTP-Redirect 跳转 URL（SP 发起 SLO）。

    Args:
        request_data: python3-saml 请求上下文
        idp_cfg: IdP 配置字典
        name_id: 用户 NameID（从登录断言中获取）
        session_index: 会话索引（从登录断言中获取）
        relay_state: RelayState 值
        strict: 是否启用严格模式

    Returns:
        str: IdP SLO URL（含 SAMLRequest + RelayState）
    """
    settings_dict = build_full_settings_dict(idp_cfg, strict=strict)
    auth = _build_auth(request_data, settings_dict)
    return auth.logout(
        name_id=name_id,
        session_index=session_index,
        return_to=relay_state,
    )


def parse_logout_response(
    request_data: Dict[str, Any],
    idp_cfg: Dict[str, Any],
    *,
    strict: bool = True,
) -> Tuple[bool, str]:
    """解析 LogoutResponse，判断 SLO 是否成功。

    IdP 返回 LogoutResponse 后，本函数：
        1. 调用 auth.process_slo() 解析并验证
        2. 检查 errors

    Args:
        request_data: python3-saml 请求上下文（get_data 需含 SAMLResponse）
        idp_cfg: IdP 配置字典
        strict: 是否启用严格模式

    Returns:
        tuple[bool, str]: (是否成功, 消息)
    """
    settings_dict = build_full_settings_dict(idp_cfg, strict=strict)
    auth = _build_auth(request_data, settings_dict)
    # process_slo 返回 True 表示 SLO 成功，False 表示有错误
    success = auth.process_slo()
    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason()
        return False, f"LogoutResponse 校验失败: errors={errors} reason={reason}"
    return True, "SLO 成功"
