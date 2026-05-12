"""
AI客户端核心基础模块

本模块定义了AI服务的基础设施层，包含三个核心部分：
1. 异常体系 — 针对AI服务各类错误的分级异常类，支持错误码标识
2. 错误检测 — 将底层HTTP/OpenAI异常自动映射为业务异常
3. 客户端基类 — 提供API配置、LRU缓存、重试策略等基础能力

依赖：
    - openai: OpenAI官方SDK
    - app.core.config.settings: 全局配置（API地址、密钥、模型名）
"""
import time
from typing import Any, Optional
from openai import OpenAI
from app.core.config import settings
from loguru import logger


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


class AIClientBase:
    """AI客户端基类

    提供AI服务调用的基础能力：
    - API配置管理：从全局settings读取API地址、密钥、模型名
    - 内存LRU缓存：避免重复请求相同内容，减少API调用开销
    - 重试策略：max_retries次重试 + retry_delay秒间隔

    缓存设计说明：
        - 使用MD5哈希生成缓存键，确保键长度固定且无冲突
        - 缓存过期时间默认3600秒（1小时）
        - 缓存容量上限MAX_CACHE_SIZE=200，满时淘汰最久未访问的条目
        - 每次写入时自动清理已过期的缓存条目

    该类作为Mixin基类使用，不单独实例化。
    """
    MAX_CACHE_SIZE = 200

    def __init__(self) -> None:
        self.api_url = settings.DEEPSEEK_API_URL
        self.api_key = settings.DEEPSEEK_API_KEY
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 2  # 重试间隔（秒）
        self.model = settings.DEEPSEEK_MODEL
        self.cache = {}  # 内存缓存字典：{cache_key: (data, timestamp)}
        self.cache_expiry = 3600  # 缓存过期时间（秒）

    def _get_cache_key(self, function_name: str, *args, **kwargs) -> str:
        """生成缓存键

        使用MD5哈希将函数名+参数组合为固定长度的键，避免超长键值问题。

        Args:
            function_name: 调用的方法名
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            str: 32位MD5哈希字符串
        """
        import hashlib
        key_data = f"{function_name}:{str(args)}:{str(kwargs)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存中获取数据

        如果缓存命中且未过期则返回数据，否则删除过期条目并返回None。

        Args:
            key: 缓存键（由_get_cache_key生成）

        Returns:
            Optional[Any]: 缓存命中返回数据，未命中或已过期返回None
        """
        if key in self.cache:
            cached_data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_expiry:
                logger.info(f"从缓存获取数据: {key}")
                return cached_data
            else:
                # 缓存已过期，主动清理
                del self.cache[key]
        return None

    def _set_to_cache(self, key: str, data: Any) -> None:
        """写入缓存

        写入前执行两项清理：
        1. 清除所有已过期的缓存条目（惰性删除）
        2. 若缓存已满，淘汰最早写入的条目（简易LRU策略）

        Args:
            key: 缓存键
            data: 要缓存的数据
        """
        now = time.time()
        # 惰性清理：遍历并删除所有过期条目
        expired_keys = [k for k, (_, ts) in self.cache.items() if now - ts >= self.cache_expiry]
        for k in expired_keys:
            del self.cache[k]
        # 容量淘汰：缓存满时移除最旧条目
        if len(self.cache) >= self.MAX_CACHE_SIZE:
            oldest_key = min(self.cache, key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (data, now)
        logger.info(f"设置缓存数据: {key}, 当前缓存大小: {len(self.cache)}")


def get_ai_client(api_key: str = None, base_url: str = None, model_name: str = None) -> OpenAI:
    """创建OpenAI客户端实例

    工厂函数，支持自定义API密钥、地址和模型名。
    未指定参数时从全局settings获取默认值。

    Args:
        api_key: API密钥，默认使用settings.DEEPSEEK_API_KEY
        base_url: API基础URL，默认使用 https://api.deepseek.com
        model_name: 模型名称，默认使用settings.DEEPSEEK_MODEL

    Returns:
        OpenAI: 配置好的OpenAI客户端实例，附带model_name属性
    """
    _api_key = api_key or settings.DEEPSEEK_API_KEY
    _base_url = base_url or "https://api.deepseek.com"
    _model_name = model_name or settings.DEEPSEEK_MODEL
    client = OpenAI(api_key=_api_key, base_url=_base_url)
    # 将模型名挂载到客户端实例上，方便后续调用时获取
    client.model_name = _model_name
    return client
