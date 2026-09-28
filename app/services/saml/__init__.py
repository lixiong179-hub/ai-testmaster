"""SAML 2.0 SSO SP 协议子包。

按职责拆分：
    - _settings_builder: 从 settings 构建 python3-saml Settings 字典
    - _protocol: AuthnRequest 生成 / Response 解析 / SP 元数据生成

主服务入口在 app.services.saml_service.SAMLService。
"""
from app.services.saml._settings_builder import (
    build_sp_settings_dict,
    build_idp_settings_dict,
    build_full_settings_dict,
)
from app.services.saml._protocol import (
    generate_sp_metadata_xml,
    build_authn_request_redirect,
    parse_saml_response,
    build_logout_request_redirect,
    parse_logout_response,
)

__all__ = [
    "build_sp_settings_dict",
    "build_idp_settings_dict",
    "build_full_settings_dict",
    "generate_sp_metadata_xml",
    "build_authn_request_redirect",
    "parse_saml_response",
    "build_logout_request_redirect",
    "parse_logout_response",
]
