"""Prompt 注册中心 - 模块级常量与工具函数。

集中维护 Prompt 版本注册中心所需的:
    - 硬编码 Prompt fallback 映射
    - 模块级 logger
    - SHA256 哈希计算工具

供同步/异步 Mixin 与 thin wrapper 复用，避免循环依赖。
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

# 硬编码 Prompt 常量映射，作为 DB 无记录时的 fallback
_HARDCODED_PROMPTS: dict[str, str] = {}


def register_hardcoded_prompt(key: str, content: str) -> None:
    """注册硬编码 Prompt 常量到 fallback 映射。

    Args:
        key: Prompt 唯一标识键。
        content: 硬编码 Prompt 内容。
    """
    _HARDCODED_PROMPTS[key] = content


def _compute_prompt_hash(content: str) -> str:
    """计算 Prompt 内容的 SHA256 哈希值。

    Args:
        content: Prompt 内容字符串。

    Returns:
        64位十六进制哈希字符串。
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
