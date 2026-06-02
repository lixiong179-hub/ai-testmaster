"""
AI 调用错误码枚举模块

本模块定义 AIInvocationGateway 审计增强所需的标准化错误码，
用于 AICallLog.error_code 字段，实现错误分类与统计聚合。

错误码设计原则：
    - 机器可读：枚举值作为 AICallLog.error_code 存储
    - 可扩展：新增错误码只需追加枚举成员
    - 与 AIServiceError 体系解耦：业务异常体系独立演进
"""
from enum import Enum


class AIErrorCode(str, Enum):
    """AI 调用错误码枚举

    每个枚举成员的 value 即为写入 AICallLog.error_code 的字符串值。
    继承 str 使其可直接序列化为 JSON 字符串，无需额外转换。
    """

    AI_TIMEOUT = "AI_TIMEOUT"
    """AI 请求超时 — 服务端未在规定时间内响应"""

    AI_RATE_LIMIT = "AI_RATE_LIMIT"
    """AI 请求频率超限 — 触发了服务端限流策略"""

    AI_INVALID_JSON = "AI_INVALID_JSON"
    """AI 响应 JSON 解析失败 — 返回内容不是合法 JSON"""

    AI_EMPTY_RESULT = "AI_EMPTY_RESULT"
    """AI 响应为空 — 模型未返回有效内容"""

    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    """AI 服务不可用 — 提供商端点不可达或返回 5xx"""

    AI_UNKNOWN_ERROR = "AI_UNKNOWN_ERROR"
    """AI 未知错误 — 未匹配到上述分类的异常"""
