"""
AI 服务异常体系模块

本模块定义了 AI 服务各类错误的分级异常类，以及将底层 HTTP/OpenAI
异常自动映射为业务异常的检测函数。所有异常均继承自 AIServiceError，
携带可读的错误信息和标准错误码，便于上层用统一的 except AIServiceError
捕获并基于 error_code 做差异化处理。

依赖：
    - 仅依赖标准库 typing，无外部 IO/网络依赖，可被任意模块安全导入。
"""
from typing import Optional


class AIServiceError(Exception):
    """AI服务基础异常

    所有AI相关业务异常的基类，携带可读的错误信息和标准错误码。
    子类应通过 error_code 提供机器可读的标识，便于上层统一处理。
    """
    def __init__(self, message: str, error_code: Optional[str] = None) -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AIAuthenticationError(AIServiceError):
    """AI API认证失败 — API密钥无效或已过期"""
    def __init__(self, message: str = "AI API认证失败，请检查API密钥") -> None:
        super().__init__(message, error_code="AUTH_FAILED")


class AIRateLimitError(AIServiceError):
    """AI API请求频率超限 — 触发了服务端限流策略"""
    def __init__(self, message: str = "AI API请求频率过高，请稍后重试") -> None:
        super().__init__(message, error_code="RATE_LIMITED")


class AIPermissionError(AIServiceError):
    """AI API权限不足 — 当前密钥无权访问指定资源"""
    def __init__(self, message: str = "AI API权限不足") -> None:
        super().__init__(message, error_code="PERMISSION_DENIED")


class AINotFoundError(AIServiceError):
    """AI API地址错误 — 请求的模型或端点不存在"""
    def __init__(self, message: str = "AI API地址错误") -> None:
        super().__init__(message, error_code="NOT_FOUND")


class AITimeoutError(AIServiceError):
    """AI API请求超时 — 服务端未在规定时间内响应"""
    def __init__(self, message: str = "AI API请求超时") -> None:
        super().__init__(message, error_code="TIMEOUT")


class AIResponseParseError(AIServiceError):
    """AI响应解析失败 — 返回内容不是合法JSON或结构不符预期"""
    def __init__(self, message: str = "AI响应格式错误，无法解析") -> None:
        super().__init__(message, error_code="PARSE_ERROR")


class AIResponseFormatError(AIServiceError):
    """AI响应缺少必要字段 — JSON可解析但业务字段缺失"""
    def __init__(self, message: str = "AI响应缺少必要字段") -> None:
        super().__init__(message, error_code="FORMAT_ERROR")


def _detect_ai_error(e: Exception) -> AIServiceError:
    """将底层异常映射为业务异常

    通过分析异常信息中的HTTP状态码和关键词，自动选择最匹配的业务异常类。
    这使得上层代码可以用统一的 except AIServiceError 捕获所有AI错误，
    并通过 error_code 做差异化处理。

    Args:
        e: 底层异常对象（通常是 openai.OpenAIError 或 requests.RequestException）

    Returns:
        AIServiceError: 映射后的业务异常，包含语义化的错误信息和标准错误码
    """
    error_str = str(e).lower()
    # 401/认证失败 → 密钥无效
    if "401" in error_str or "unauthorized" in error_str or "authentication fails" in error_str:
        return AIAuthenticationError()
    # 429/限流 → 请求过快
    elif "429" in error_str or "rate limit" in error_str:
        return AIRateLimitError()
    # 403/禁止 → 权限不足
    elif "403" in error_str or "forbidden" in error_str:
        return AIPermissionError()
    # 404/未找到 → 端点或模型不存在
    elif "404" in error_str or "not found" in error_str:
        return AINotFoundError()
    # 超时 → 服务端响应过慢
    elif "timeout" in error_str:
        return AITimeoutError()
    # 其他未分类错误
    else:
        return AIServiceError(f"AI服务错误: {str(e)}")
