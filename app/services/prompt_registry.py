"""Prompt 版本注册中心 - Prompt 模板的版本管理、默认切换与回滚。

核心能力:
    - get_prompt: 按 key + version 获取，version 省略时取默认版本
    - register_prompt: 注册新版本，自动递增版本号、计算 SHA256 哈希
    - set_default: 切换默认版本（先取消旧默认再设新默认）
    - rollback: 回滚到指定版本（设为默认并禁用更高版本）
    - list_versions: 列出某 key 的所有版本
    - get_prompt_content: 优先从 DB 读取，DB 无记录时 fallback 到硬编码常量
"""
import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate

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


class PromptRegistry:
    """Prompt 版本注册中心，封装 Prompt 模板的版本管理逻辑。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_prompt(self, key: str, version: Optional[int] = None) -> Optional[PromptTemplate]:
        """获取 Prompt 模板记录。

        Args:
            key: Prompt 唯一标识键。
            version: 版本号，为 None 时获取 is_default=True 的版本。

        Returns:
            匹配的 PromptTemplate 实例，未找到返回 None。
        """
        query = self._db.query(PromptTemplate).filter(
            PromptTemplate.prompt_key == key,
            PromptTemplate.enabled.is_(True),
        )
        if version is not None:
            query = query.filter(PromptTemplate.prompt_version == version)
        else:
            query = query.filter(PromptTemplate.is_default.is_(True))

        return query.first()

    def register_prompt(
        self,
        key: str,
        content: str,
        description: Optional[str] = None,
    ) -> PromptTemplate:
        """注册 Prompt 新版本，自动递增版本号并计算哈希。

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

        # 计算下一个版本号
        maxVersion = (
            self._db.query(PromptTemplate.prompt_version)
            .filter(PromptTemplate.prompt_key == key)
            .order_by(PromptTemplate.prompt_version.desc())
            .first()
        )
        next_version = (maxVersion[0] + 1) if maxVersion else 1

        # 内容与最新版本相同时拒绝重复注册
        if maxVersion:
            latest = (
                self._db.query(PromptTemplate)
                .filter(
                    PromptTemplate.prompt_key == key,
                    PromptTemplate.prompt_version == maxVersion[0],
                )
                .first()
            )
            if latest and latest.prompt_hash == prompt_hash:
                raise ValueError(
                    f"Prompt key='{key}' 最新版本 v{latest.prompt_version} "
                    f"内容与本次注册完全相同，拒绝重复注册"
                )

        # 判断是否需要设为默认（该 key 无默认版本时）
        hasDefault = (
            self._db.query(PromptTemplate)
            .filter(
                PromptTemplate.prompt_key == key,
                PromptTemplate.is_default.is_(True),
            )
            .first()
        )

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
        self._db.flush()

        logger.info(
            f"注册 Prompt: key='{key}', version={next_version}, "
            f"hash={prompt_hash[:16]}..., is_default={template.is_default}"
        )
        return template

    def set_default(self, key: str, version: int) -> PromptTemplate:
        """将指定版本设为默认版本，先取消旧默认。

        Args:
            key: Prompt 唯一标识键。
            version: 要设为默认的版本号。

        Returns:
            设为默认的 PromptTemplate 实例。

        Raises:
            ValueError: 指定版本不存在时抛出。
        """
        target = (
            self._db.query(PromptTemplate)
            .filter(
                PromptTemplate.prompt_key == key,
                PromptTemplate.prompt_version == version,
            )
            .first()
        )
        if not target:
            raise ValueError(f"Prompt key='{key}' 版本 v{version} 不存在")

        # 取消旧默认
        self._db.query(PromptTemplate).filter(
            PromptTemplate.prompt_key == key,
            PromptTemplate.is_default.is_(True),
        ).update({PromptTemplate.is_default: False}, synchronize_session="fetch")

        # 设为新默认
        target.is_default = True
        self._db.flush()

        logger.info(f"切换默认版本: key='{key}', version={version}")
        return target

    def rollback(self, key: str, target_version: int) -> PromptTemplate:
        """回滚到指定版本：设为默认并禁用更高版本。

        Args:
            key: Prompt 唯一标识键。
            target_version: 回滚目标版本号。

        Returns:
            回滚目标版本的 PromptTemplate 实例。

        Raises:
            ValueError: 目标版本不存在时抛出。
        """
        target = (
            self._db.query(PromptTemplate)
            .filter(
                PromptTemplate.prompt_key == key,
                PromptTemplate.prompt_version == target_version,
            )
            .first()
        )
        if not target:
            raise ValueError(f"Prompt key='{key}' 版本 v{target_version} 不存在")

        # 禁用更高版本
        self._db.query(PromptTemplate).filter(
            PromptTemplate.prompt_key == key,
            PromptTemplate.prompt_version > target_version,
        ).update({PromptTemplate.enabled: False}, synchronize_session="fetch")

        # 取消旧默认并设目标为默认
        self._db.query(PromptTemplate).filter(
            PromptTemplate.prompt_key == key,
            PromptTemplate.is_default.is_(True),
        ).update({PromptTemplate.is_default: False}, synchronize_session="fetch")

        target.is_default = True
        target.enabled = True
        self._db.flush()

        logger.info(f"回滚 Prompt: key='{key}', target_version={target_version}")
        return target

    def list_versions(self, key: str) -> list[PromptTemplate]:
        """列出指定 key 的所有版本，按版本号升序排列。

        Args:
            key: Prompt 唯一标识键。

        Returns:
            PromptTemplate 列表。
        """
        return (
            self._db.query(PromptTemplate)
            .filter(PromptTemplate.prompt_key == key)
            .order_by(PromptTemplate.prompt_version.asc())
            .all()
        )

    def get_prompt_content(self, key: str) -> str:
        """获取 Prompt 内容，优先从 DB 读取，DB 无记录时 fallback 到硬编码常量。

        Args:
            key: Prompt 唯一标识键。

        Returns:
            Prompt 内容字符串，DB 和硬编码均无记录时返回空字符串。
        """
        template = self.get_prompt(key)
        if template:
            return template.content

        fallback = _HARDCODED_PROMPTS.get(key, "")
        if fallback:
            logger.debug(f"Prompt key='{key}' DB 无记录，使用硬编码 fallback")
        else:
            logger.warning(f"Prompt key='{key}' DB 无记录且无硬编码 fallback")
        return fallback
