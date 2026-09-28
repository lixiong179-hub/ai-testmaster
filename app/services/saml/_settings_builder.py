"""SAML SP/IdP 设置字典构建器。

将 app.core.config.settings 中的 SAML_* 配置项转换为 python3-saml
所需的 Settings 字典格式。python3-saml 的 OneLogin_Saml2_Settings 接受
严格的字典结构，本模块负责适配。

设计要点：
    - SP 配置从全局 settings 读取（SAML_SP_ENTITY_ID / SAML_SP_X509_CERT 等）
    - IdP 配置从 SAML_IDP_CONFIGS 中按 provider 查找
    - 证书/私钥支持 PEM 格式（含 BEGIN/END 标记）或纯 base64
    - nameid_format 默认 urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress
"""
from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings

# SAML NameID 格式常量（OASIS 标准）
NAMEID_FORMAT_UNSPECIFIED = "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"
NAMEID_FORMAT_EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
NAMEID_FORMAT_TRANSIENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:transient"
NAMEID_FORMAT_PERSISTENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"

# 默认 NameID 格式（邮箱地址，兼容 Okta/Azure AD 常见配置）
DEFAULT_NAMEID_FORMAT = NAMEID_FORMAT_EMAIL


def _normalize_pem(content: str, is_cert: bool = True) -> str:
    """规范化证书/私钥内容为 PEM 格式。

    python3-saml 要求 PEM 格式（含 BEGIN/END 标记）。
    若输入为纯 base64，自动补齐 PEM 标记。

    Args:
        content: 证书/私钥内容（PEM 或纯 base64）
        is_cert: True 为证书，False 为私钥

    Returns:
        str: 规范化的 PEM 内容
    """
    if not content or not content.strip():
        return ""
    content = content.strip()
    if "BEGIN" in content:
        return content
    label = "CERTIFICATE" if is_cert else "PRIVATE KEY"
    return f"-----BEGIN {label}-----\n{content}\n-----END {label}-----"


def build_sp_settings_dict() -> Dict[str, Any]:
    """构建 python3-saml 的 SP（Service Provider）Settings 字典。

    从全局 settings 读取 SP 配置（entity_id / acs_url / slo_url / 证书 / 私钥），
    返回 python3-saml OneLogin_Saml2_Settings 所需的 sp 字段。

    Returns:
        dict: SP 设置字典，含 entityId/url/x509cert/privateKey
    """
    return {
        "entityId": settings.SAML_SP_ENTITY_ID,
        "assertionConsumerService": {
            "url": settings.SAML_SP_ACS_URL,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        },
        "singleLogoutService": {
            "url": settings.SAML_SP_SLO_URL,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": _normalize_pem(settings.SAML_SP_X509_CERT, is_cert=True),
        "privateKey": _normalize_pem(settings.SAML_SP_PRIVATE_KEY, is_cert=False),
    }


def build_idp_settings_dict(idp_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """构建 python3-saml 的 IdP（Identity Provider）Settings 字典。

    从单个 IdP 配置字典读取 entity_id / sso_url / slo_url / x509_cert，
    返回 python3-saml OneLogin_Saml2_Settings 所需的 idp 字段。

    Args:
        idp_cfg: IdP 配置字典（含 entity_id/sso_url/slo_url/x509_cert/nameid_format）

    Returns:
        dict: IdP 设置字典，含 entityId/singleSignOnService/singleLogoutService/x509cert
    """
    nameid_format = idp_cfg.get("nameid_format", DEFAULT_NAMEID_FORMAT)
    return {
        "entityId": idp_cfg.get("entity_id", ""),
        "singleSignOnService": {
            "url": idp_cfg.get("sso_url", ""),
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "singleLogoutService": {
            "url": idp_cfg.get("slo_url", ""),
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": _normalize_pem(idp_cfg.get("x509_cert", ""), is_cert=True),
        "NameIDFormat": nameid_format,
    }


def build_full_settings_dict(idp_cfg: Dict[str, Any], *, strict: bool = True) -> Dict[str, Any]:
    """构建完整的 python3-saml Settings 字典（SP + IdP + security）。

    Args:
        idp_cfg: IdP 配置字典
        strict: 是否启用严格模式（生产环境建议 True，测试可 False 放宽）

    Returns:
        dict: 完整的 Settings 字典，可直接传给 OneLogin_Saml2_Settings
    """
    sp = build_sp_settings_dict()
    idp = build_idp_settings_dict(idp_cfg)
    return {
        "strict": strict,
        "debug": settings.DEBUG,
        "sp": sp,
        "idp": idp,
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": idp_cfg.get("sign_authn_request", False),
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantMessagesSigned": idp_cfg.get("want_messages_signed", True),
            "wantAssertionsSigned": idp_cfg.get("want_assertions_signed", True),
            "wantAssertionsEncrypted": False,
            "wantNameId": True,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }
