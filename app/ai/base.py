"""
AI 客户端基类与工厂模块

本模块提供 AI 服务调用的基础能力：
1. AIClientBase — 客户端基类（Mixin），提供 API 配置管理、内存 LRU 缓存、
   重试策略等基础能力，作为各业务 Mixin 的基类使用，不单独实例化。
2. get_ai_client — 工厂函数，创建配置好的 OpenAI 客户端实例。

依赖：
    - openai: OpenAI 官方 SDK
    - app.core.config.settings: 全局配置（API 地址、密钥、模型名）
"""
import time
from typing import Any, Optional

from openai import OpenAI
from loguru import logger

from app.core.config import settings


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
                logger.debug(f"从缓存获取数据: {key}")
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
        logger.debug(f"设置缓存数据: {key}, 当前缓存大小: {len(self.cache)}")


def get_ai_client(api_key: str = None, base_url: str = None, model_name: str = None, timeout: int = None) -> OpenAI:
    """创建OpenAI客户端实例

    工厂函数，支持自定义API密钥、地址和模型名。
    未指定参数时从全局settings获取默认值。

    Args:
        api_key: API密钥，默认使用settings.DEEPSEEK_API_KEY
        base_url: API基础URL，默认使用 https://api.deepseek.com
        model_name: 模型名称，默认使用settings.DEEPSEEK_MODEL
        timeout: 请求超时秒数，默认使用TimeoutConfig.AI_API

    Returns:
        OpenAI: 配置好的OpenAI客户端实例，附带model_name属性
    """
    from app.core.constants import TimeoutConfig
    _api_key = api_key or settings.DEEPSEEK_API_KEY
    _base_url = base_url or "https://api.deepseek.com"
    _model_name = model_name or settings.DEEPSEEK_MODEL
    _timeout = timeout or TimeoutConfig.AI_API
    client = OpenAI(api_key=_api_key, base_url=_base_url, timeout=_timeout)
    client.model_name = _model_name
    return client
