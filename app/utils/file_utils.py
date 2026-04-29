"""
文件工具模块

提供文件格式验证、MIME类型检测、URL安全校验等文件处理功能。
核心目标是确保上传文件的安全性和类型正确性。

安全设计要点：
1. 格式白名单：仅允许SUPPORTED_FILE_TYPES中定义的文件格式上传
2. MIME校验：验证文件实际MIME类型与扩展名是否匹配，防止伪装攻击
3. 危险类型拦截：DANGEROUS_MIMES中的可执行文件类型直接拒绝
4. SSRF防护：URL验证时检测并拦截内网地址（私有IP、回环地址、链路本地地址）
5. 压缩包特殊处理：zip/rar的MIME变体较多，使用ARCHIVE_MIME_VARIANTS集合匹配

资源类型自动识别：
    根据文件名关键词和扩展名，将文件自动归类为：
    - requirement: 需求文档（docx/doc/pdf/txt/md）
    - ui_mockup: UI原型图（png/jpg/jpeg/gif/webp）
    - api_doc: API文档（yaml/yml/json）
    - test_data: 测试数据（xlsx/xls/csv）
    - other: 其他类型

核心函数：
    - validate_file_format: 验证文件扩展名是否在白名单中
    - detect_resource_type: 根据文件名和扩展名自动识别资源类型
    - validate_file_mime: 验证MIME类型与扩展名是否匹配
    - validate_url: 验证URL可访问性（含SSRF防护）
    - get_file_size: 获取文件大小（KB）
    - parse_file: 解析文件基础信息
    - parse_url: 解析URL基础信息

依赖：
    - ipaddress: IP地址解析（SSRF防护）
    - socket: DNS解析（SSRF防护）
    - requests: URL可达性验证
"""
import os
import ipaddress
import socket
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse

# 支持的文件格式白名单 — 扩展名到MIME类型的映射
SUPPORTED_FILE_TYPES = {
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword',
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
    'csv': 'text/csv',
    'txt': 'text/plain',
    'md': 'text/markdown',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'figma': 'application/json',
    'url': 'text/plain',
    'yaml': 'text/yaml',
    'yml': 'text/yaml',
    'json': 'application/json',
    'zip': 'application/zip',
    'rar': 'application/vnd.rar',
}

# 压缩包扩展名集合 — 需要特殊MIME匹配逻辑
ARCHIVE_EXTENSIONS = {'zip', 'rar'}

# 压缩包MIME变体 — 不同系统/浏览器对同一压缩格式的MIME声明可能不同
ARCHIVE_MIME_VARIANTS = {
    'zip': {'application/zip', 'application/x-zip-compressed', 'application/x-zip'},
    'rar': {'application/vnd.rar', 'application/x-rar-compressed', 'application/x-rar'},
}

# 危险MIME类型黑名单 — 可执行文件、脚本等，禁止上传
DANGEROUS_MIMES = {
    'application/x-executable', 'application/x-msdos-program',
    'application/x-shellscript', 'application/x-python-code',
    'application/javascript', 'text/x-php',
    'application/x-bat', 'application/x-msdownload',
}

# 资源类型关键词映射 — 文件名中包含这些关键词时自动归类到对应资源类型
RESOURCE_TYPE_KEYWORDS = {
    'requirement': ['需求', 'requirement', 'spec', '规格', 'prd', 'brd'],
    'ui_mockup': ['ui', '原型', 'mockup', '设计', 'design', 'figma', 'axure', '图'],
    'api_doc': ['api', '接口', 'swagger', 'openapi'],
    'test_data': ['测试数据', 'testdata', '用例'],
}

# 扩展名到资源类型的默认映射 — 当文件名无关键词匹配时的回退策略
EXTENSION_RESOURCE_MAP = {
    'docx': 'requirement', 'doc': 'requirement', 'pdf': 'requirement',
    'txt': 'requirement', 'md': 'requirement',
    'png': 'ui_mockup', 'jpg': 'ui_mockup', 'jpeg': 'ui_mockup',
    'gif': 'ui_mockup', 'webp': 'ui_mockup',
    'yaml': 'api_doc', 'yml': 'api_doc', 'json': 'api_doc',
    'xlsx': 'test_data', 'xls': 'test_data', 'csv': 'test_data',
}


def validate_file_format(file_name: str) -> Optional[str]:
    """
    验证文件格式是否支持
    
    Args:
        file_name: 文件名
    
    Returns:
        Optional[str]: 支持的文件类型，否则返回None
    """
    if not file_name or '.' not in file_name:
        return None
    ext = file_name.rsplit('.', 1)[-1].lower()
    if ext in SUPPORTED_FILE_TYPES:
        return ext
    return None


def detect_resource_type(filename: str, file_ext: str) -> str:
    """
    根据文件名和扩展名自动识别资源类型

    优先级：文件名关键词 > 扩展名默认映射 > other
    对于压缩包文件，仅通过文件名关键词推断，无匹配则返回 other

    Args:
        filename: 文件名
        file_ext: 文件扩展名（小写）

    Returns:
        str: 资源类型（requirement/ui_mockup/api_doc/test_data/other）
    """
    filename_lower = filename.lower()

    for resource_type, keywords in RESOURCE_TYPE_KEYWORDS.items():
        if any(keyword in filename_lower for keyword in keywords):
            return resource_type

    if file_ext in ARCHIVE_EXTENSIONS:
        return "other"

    return EXTENSION_RESOURCE_MAP.get(file_ext, "other")


def validate_file_mime(file_ext: str, detected_mime: str) -> Optional[str]:
    """
    验证文件MIME类型是否与扩展名匹配

    Args:
        file_ext: 文件扩展名（小写）
        detected_mime: python-magic 检测到的实际 MIME 类型

    Returns:
        Optional[str]: 验证失败时返回错误信息，成功返回 None
    """
    if detected_mime in DANGEROUS_MIMES:
        return "检测到危险文件类型，禁止上传"

    expected_mime = SUPPORTED_FILE_TYPES.get(file_ext, "")

    if file_ext in ARCHIVE_EXTENSIONS:
        allowed_mimes = ARCHIVE_MIME_VARIANTS.get(file_ext, set())
        if detected_mime not in allowed_mimes:
            return f"压缩包MIME类型不匹配: 扩展名=.{file_ext}, 实际类型={detected_mime}"
        return None

    if expected_mime and detected_mime and not detected_mime.startswith(
        tuple(expected_mime.split('/')[:1])
    ):
        return f"文件MIME类型不匹配: 扩展名=.{file_ext}, 声明={expected_mime}, 实际={detected_mime}"

    return None


def validate_url(url: str) -> bool:
    """验证URL是否可访问（含SSRF防护）

    执行三层安全检查：
    1. 协议检查：仅允许http/https协议
    2. SSRF防护：DNS解析后检查目标IP是否为内网地址
       （私有IP、回环地址、保留地址、链路本地地址均被拦截）
    3. 可达性检查：发送GET请求验证HTTP状态码<400
       同时拒绝重定向响应（防止开放重定向攻击）

    Args:
        url: 待验证的URL链接

    Returns:
        bool: URL安全且可访问返回True，否则返回False
    """
    try:
        parsed = urlparse(url)
        # 第一层：仅允许http/https协议
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # 第二层：SSRF防护 — 检查DNS解析后的IP是否为内网地址
        try:
            resolved_ips = socket.getaddrinfo(hostname, None)
            for _, _, _, _, sockaddr in resolved_ips:
                ip = ipaddress.ip_address(sockaddr[0])
                # 拦截私有IP、回环地址、保留地址、链路本地地址
                if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                    return False
        except (socket.gaierror, ValueError):
            return False

        # 第三层：可达性检查 — 拒绝重定向，验证状态码
        response = requests.get(url, timeout=10, allow_redirects=False)
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            return False
        return response.status_code < 400
    except Exception:
        return False


def get_file_size(file_path: str) -> int:
    """
    获取文件大小（单位KB）
    
    Args:
        file_path: 文件路径
    
    Returns:
        int: 文件大小（KB）
    """
    if os.path.exists(file_path):
        return os.path.getsize(file_path) // 1024
    return 0


def parse_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """
    解析文件内容
    
    Args:
        file_path: 文件路径
        file_type: 文件类型
    
    Returns:
        Dict[str, Any]: 解析结果
    """
    # 这里实现不同文件类型的解析逻辑
    # 目前返回基础信息，实际项目中可以根据需要扩展
    return {
        'file_path': file_path,
        'file_type': file_type,
        'file_size': get_file_size(file_path)
    }


def parse_url(url: str) -> Dict[str, Any]:
    """
    解析URL内容
    
    Args:
        url: URL链接
    
    Returns:
        Dict[str, Any]: 解析结果
    """
    # 这里实现URL解析逻辑
    # 目前返回基础信息，实际项目中可以根据需要扩展
    return {
        'url': url,
        'is_accessible': validate_url(url)
    }
