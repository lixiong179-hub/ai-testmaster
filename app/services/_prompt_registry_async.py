"""Prompt 注册中心 - 异步方法 Mixin。

封装 PromptTemplate 的异步版本管理逻辑（基于 select() + await db.execute()），
供 PromptRegistry 通过多继承组合使用，供 prompt_template endpoint 调用。

方法:
    - register_prompt_async: 异步注册新版本
    - set_default_async: 异步切换默认版本
    - rollback_async: 异步回滚到指定版本
    - list_versions_async: 异步列出所有版本
"""
from typing import Optional

from sqlalchemy import asc, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate
from app.services._prompt_registry_helpers import (
    _compute_prompt_hash,
    logger,
)


class _PromptRegistryAsyncMixin:
    """PromptRegistry 异步能力 Mixin，依赖宿主类提供 self._db (AsyncSession)。"""

    _db: AsyncSession

    async def register_prompt_async(
        self,
        key: str,
        content: str,
        description: Optional[str] = None,
    ) -> PromptTemplate:
        """异步注册 Prompt 新版本，自动递增版本号并计算哈希。

        若该 key 无默认版本，则自动将新注册版本设为默认。

        Args:
            key: Prompt 唯一标识键。
            content: Prompt 内容。
            description: 版本描述，可选。

        Returns:
            新创建的 PromptTemplate 实例。

        Raises:
            ValueError: 内容与最新版本完全相同时拒绝注册。
        """
        prompt_hash = _compute_prompt_hash(content)

        maxVersionStmt = (
            select(PromptTemplate.prompt_version)
            .where(PromptTemplate.prompt_key == key)
            .order_by(desc(PromptTemplate.prompt_version))
        )
        maxVersion = (await self._db.execute(maxVersionStmt)).first()
        next_version = (maxVersion[0] + 1) if maxVersion else 1

        if maxVersion:
            latestStmt = select(PromptTemplate).where(
                PromptTemplate.prompt_key == key,
                PromptTemplate.prompt_version == maxVersion[0],
            )
            latest = (await self._db.execute(latestStmt)).scalar_one_or_none()
            if latest and latest.prompt_hash == prompt_hash:
                raise ValueError(
                    f"Prompt key='{key}' 最新版本 v{latest.prompt_version} "
                    f"内容与本次注册完全相同，拒绝重复注册"
                )

        hasDefaultStmt = select(PromptTemplate).where(
            PromptTemplate.prompt_key == key,
            PromptTemplate.is_default.is_(True),
        )
        hasDefault = (await self._db.execute(hasDefaultStmt)).scalar_one_or_none()

        template = PromptTemplate(
            prompt_key=key,
            prompt_version=next_version,
            prompt_hash=prompt_hash,
            content=content,
            enabled=True,
            is_default=(hasDefault is None),
            description=description,
        )
        self._db.add(template)
        await self._db.flush()
        await self._db.refresh(template)

        logger.info(
            f"注册 Prompt: key='{key}', version={next_version}, "
            f"hash={prompt_hash[:16]}..., is_default={template.is_default}"
        )
        return template

    async def set_default_async(self, key: str, version: int) -> PromptTemplate:
        """异步将指定版本设为默认版本，先取消旧默认。

        Args:
            key: Prompt 唯一标识键。
            version: 要设为默认的版本号。

        Returns:
            设为默认的 PromptTemplate 实例。

        Raises:
            ValueError: 指定版本不存在时抛出。
        """
        targetStmt = select(PromptTemplate).where(
            PromptTemplate.prompt_key == key,
            PromptTemplate.prompt_version == version,
        )
        target = (await self._db.execute(targetStmt)).scalar_one_or_none()
        if not target:
            raise ValueError(f"Prompt key='{key}' 版本 v{version} 不存在")

        await self._db.execute(
            update(PromptTemplate)
            .where(
                PromptTemplate.prompt_key == key,
                PromptTemplate.is_default.is_(True),
            )
            .values(is_default=False)
        )

        target.is_default = True
        await self._db.flush()

        logger.info(f"切换默认版本: key='{key}', version={version}")
        return target

    async def rollback_async(self, key: str, target_version: int) -> PromptTemplate:
        """异步回滚到指定版本：设为默认并禁用更高版本。

        Args:
            key: Prompt 唯一标识键。
            target_version: 回滚目标版本号。

        Returns:
            回滚目标版本的 PromptTemplate 实例。

        Raises:
            ValueError: 目标版本不存在时抛出。
        """
        targetStmt = select(PromptTemplate).where(
            PromptTemplate.prompt_key == key,
            PromptTemplate.prompt_version == target_version,
        )
        target = (await self._db.execute(targetStmt)).scalar_one_or_none()
        if not target:
            raise ValueError(f"Prompt key='{key}' 版本 v{target_version} 不存在")

        await self._db.execute(
            update(PromptTemplate)
            .where(
                PromptTemplate.prompt_key == key,
                PromptTemplate.prompt_version > target_version,
            )
            .values(enabled=False)
        )

        await self._db.execute(
            update(PromptTemplate)
            .where(
                PromptTemplate.prompt_key == key,
                PromptTemplate.is_default.is_(True),
            )
            .values(is_default=False)
        )

        target.is_default = True
        target.enabled = True
        await self._db.flush()

        logger.info(f"回滚 Prompt: key='{key}', target_version={target_version}")
        return target

    async def list_versions_async(self, key: str) -> list[PromptTemplate]:
        """异步列出指定 key 的所有版本，按版本号升序排列。

        Args:
            key: Prompt 唯一标识键。

        Returns:
            PromptTemplate 列表。
        """
        stmt = (
            select(PromptTemplate)
            .where(PromptTemplate.prompt_key == key)
            .order_by(asc(PromptTemplate.prompt_version))
        )
        return list((await self._db.execute(stmt)).scalars().all())
