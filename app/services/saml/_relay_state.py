"""SAML RelayState 存储管理。

封装 RelayState 的生成、存储、消费与清理，支持 Redis（生产）与内存（降级）两种后端。

RelayState 用途：
    1. CSRF 防护：SP 发起 SSO 时生成随机 RelayState，IdP 回调时原样回传，
       SP 校验 RelayState 是否存在以防止跨站请求伪造
    2. 请求上下文保持：存储 provider 标识与 redirect_to 路径，
       ACS 回调后用于路由到正确的 IdP 配置与前端跳转目标

设计要点：
    - 一次性消费：消费后立即删除，防止重放攻击
    - TTL 控制：默认 600 秒过期，与 SAML_RELAYSTATE_TTL_SECONDS 配置一致
    - Redis 降级：Redis 不可用时自动降级到进程内内存存储
"""
from __future__ import annotations

import json
import secrets
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.core.config import settings


def _get_redis_client():
    """延迟获取 Redis 客户端，复用 jwt_utils 的连接配置。

    返回 None 表示 Redis 不可用，调用方应降级到内存存储。
    """
    try:
        import redis
        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            return None
        return redis.from_url(
            redis_url,
            max_connections=10,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    except Exception as e:
        logger.debug(f"Redis 不可用，SAML RelayState 降级为内存模式: {e}")
        return None


# 进程内 RelayState 存储（Redis 不可用时的降级方案）
# 结构：{relay_state: {"provider": str, "redirect_to": str, "expires_at": float}}
_memory_relay_store: Dict[str, Dict[str, Any]] = {}


class RelayStateStore:
    """RelayState 存储管理器。

    支持 Redis（多实例共享）与内存（单实例降级）两种后端，
    自动选择可用后端，提供统一的生成 / 存储 / 消费接口。

    使用示例：
        store = RelayStateStore()
        relay_state = store.generate()
        store.save(relay_state, "okta", "/dashboard")
        # ACS 回调时
        payload = store.consume(relay_state)
        if payload is None:
            raise SAMLRelayStateError("RelayState 已过期或不存在")
    """

    REDIS_PREFIX = "saml:relay:"

    def generate(self) -> str:
        """生成 CSRF 防护用的 RelayState 参数（256-bit 随机）。"""
        return secrets.token_urlsafe(32)

    def save(
        self,
        relay_state: str,
        provider: str,
        redirect_to: Optional[str] = None,
    ) -> None:
        """存储 RelayState → (provider, redirect_to) 映射，带 TTL。

        Args:
            relay_state: RelayState 值
            provider: IdP 标识
            redirect_to: 登录成功后前端跳转目标路径
        """
        expires_at = time.time() + settings.SAML_RELAYSTATE_TTL_SECONDS
        payload = {
            "provider": provider,
            "redirect_to": redirect_to or "",
            "expires_at": expires_at,
        }
        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                redis_client.setex(
                    f"{self.REDIS_PREFIX}{relay_state}",
                    settings.SAML_RELAYSTATE_TTL_SECONDS,
                    json.dumps(payload),
                )
                return
            except Exception as e:
                logger.warning(f"Redis 存储 RelayState 失败，降级为内存: {e}")
        _memory_relay_store[relay_state] = payload
        self._cleanup_memory()

    def consume(self, relay_state: str) -> Optional[Dict[str, Any]]:
        """消费 RelayState（一次性读取后删除），返回存储的 payload。

        Args:
            relay_state: RelayState 值

        Returns:
            Optional[dict]: payload 含 provider/redirect_to/expires_at；
                           不存在、已过期或已被消费返回 None
        """
        if not relay_state:
            return None
        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                key = f"{self.REDIS_PREFIX}{relay_state}"
                raw = redis_client.get(key)
                if raw is None:
                    return None
                redis_client.delete(key)
                payload = json.loads(raw)
                if payload.get("expires_at", 0) < time.time():
                    return None
                return payload
            except Exception as e:
                logger.warning(f"Redis 读取 RelayState 失败，降级为内存: {e}")
        payload = _memory_relay_store.pop(relay_state, None)
        if payload is None:
            return None
        if payload.get("expires_at", 0) < time.time():
            return None
        return payload

    def _cleanup_memory(self) -> None:
        """清理内存中过期的 RelayState 条目。"""
        now = time.time()
        expired = [k for k, v in _memory_relay_store.items() if v.get("expires_at", 0) < now]
        for k in expired:
            _memory_relay_store.pop(k, None)
