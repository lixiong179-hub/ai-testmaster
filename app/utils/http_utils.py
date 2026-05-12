"""HTTP工具模块 - 提供HTTP请求相关的共享工具函数。

本模块集中管理HTTP请求中重复使用的工具函数和常量，
消除多个服务文件中的重复逻辑，提高可维护性。

核心函数:
    - build_auth_headers: 根据认证类型构建HTTP请求头

核心常量:
    - AUTH_FAILURE_KEYWORDS: 认证失败关键词（从constants导入）
"""
import base64
from typing import Dict, Any


def build_auth_headers(auth_type: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
    """根据认证类型构建HTTP请求头。

    支持Basic Auth、Bearer Token、API Key、Cookie四种认证方式，
    未匹配的认证类型仅返回基础请求头。

    Args:
        auth_type: 认证类型，可选值: "basic"/"bearer"/"api_key"/"cookie"/"none"
        auth_config: 认证配置字典，不同类型需要不同的键:
            - basic: {"username": str, "password": str}
            - bearer: {"token": str}
            - api_key: {"api_key": str, "api_key_header": str}  (api_key_header默认"X-API-Key")
            - cookie: {"cookie": str}

    Returns:
        Dict[str, str]: 包含认证信息的HTTP请求头字典
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }

    if auth_type == "basic":
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if username and password:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

    elif auth_type == "bearer":
        token = auth_config.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    elif auth_type == "api_key":
        api_key = auth_config.get("api_key", "")
        header_name = auth_config.get("api_key_header", "X-API-Key")
        if api_key:
            headers[header_name] = api_key

    elif auth_type == "cookie":
        cookie = auth_config.get("cookie", "")
        if cookie:
            headers["Cookie"] = cookie

    return headers
