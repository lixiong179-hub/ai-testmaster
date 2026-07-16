"""Prompt 版本注册中心 - Prompt 模板的版本管理、默认切换与回滚。

核心能力:
    - get_prompt: 按 key + version 获取，version 省略时取默认版本
    - register_prompt: 注册新版本，自动递增版本号、计算 SHA256 哈希
    - set_default: 切换默认版本（先取消旧默认再设新默认）
    - rollback: 回滚到指定版本（设为默认并禁用更高版本）
    - list_versions: 列出某 key 的所有版本
    - get_prompt_content: 优先从 DB 读取，DB 无记录时 fallback 到硬编码常量

迁移说明:
    sync 版本保留供 PromptBuilder 运行时（get_prompt/get_prompt_content）和
    seed 脚本（register_prompt）调用；新增 async 版本供 prompt_template
    endpoint 调用，使用 select() + await db.execute() 模式。

实现拆分:
    本文件为 thin wrapper，通过多继承组合同步/异步 Mixin，保持公开 API
    （from app.services.prompt_registry import xxx）不变。具体实现位于:
    - _prompt_registry_helpers: 模块级常量、logger、哈希工具
    - _prompt_registry_sync: 同步方法 Mixin（基于 Session.query）
    - _prompt_registry_async: 异步方法 Mixin（基于 select + await）
"""
from typing import Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.services._prompt_registry_async import _PromptRegistryAsyncMixin
from app.services._prompt_registry_helpers import (
    _HARDCODED_PROMPTS,
    _compute_prompt_hash,
    logger,
    register_hardcoded_prompt,
)
from app.services._prompt_registry_sync import _PromptRegistrySyncMixin

__all__ = [
    "PromptRegistry",
    "register_hardcoded_prompt",
    "_HARDCODED_PROMPTS",
    "_compute_prompt_hash",
    "logger",
]


class PromptRegistry(
    _PromptRegistrySyncMixin,
    _PromptRegistryAsyncMixin,
):
    """Prompt 版本注册中心，封装 Prompt 模板的版本管理逻辑。

    通过组合同步/异步 Mixin 提供完整能力:
        - 同步方法（Session）: get_prompt/register_prompt/set_default/
          rollback/list_versions/get_prompt_content
        - 异步方法（AsyncSession）: register_prompt_async/set_default_async/
          rollback_async/list_versions_async
    """

    def __init__(self, db: Union[Session, AsyncSession]) -> None:
        self._db = db
