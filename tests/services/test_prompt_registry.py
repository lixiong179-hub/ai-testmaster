"""PromptRegistry 服务测试 - 版本递增、哈希计算、默认切换、回滚、fallback 到硬编码。"""
import hashlib

import pytest
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate
from app.services.prompt_registry import PromptRegistry, register_hardcoded_prompt, _HARDCODED_PROMPTS


class TestPromptRegistry:
    """PromptRegistry 核心逻辑测试"""

    def test_register_first_version_auto_default(self, db: Session) -> None:
        """首次注册自动设为默认版本"""
        registry = PromptRegistry(db)
        template = registry.register_prompt("TEST_KEY", "hello world")

        assert template.prompt_key == "TEST_KEY"
        assert template.prompt_version == 1
        assert template.is_default is True
        assert template.enabled is True
        assert template.prompt_hash == hashlib.sha256(b"hello world").hexdigest()

    def test_register_version_auto_increment(self, db: Session) -> None:
        """版本号自动递增"""
        registry = PromptRegistry(db)
        v1 = registry.register_prompt("INC_KEY", "version 1")
        v2 = registry.register_prompt("INC_KEY", "version 2")
        v3 = registry.register_prompt("INC_KEY", "version 3")

        assert v1.prompt_version == 1
        assert v2.prompt_version == 2
        assert v3.prompt_version == 3
        # 仅首个版本为默认
        assert v1.is_default is True
        assert v2.is_default is False
        assert v3.is_default is False

    def test_register_duplicate_content_rejected(self, db: Session) -> None:
        """内容与最新版本相同时拒绝重复注册"""
        registry = PromptRegistry(db)
        registry.register_prompt("DUP_KEY", "same content")

        with pytest.raises(ValueError, match="内容与本次注册完全相同"):
            registry.register_prompt("DUP_KEY", "same content")

    def test_register_different_key_independent(self, db: Session) -> None:
        """不同 key 的版本号独立递增"""
        registry = PromptRegistry(db)
        a1 = registry.register_prompt("KEY_A", "a v1")
        b1 = registry.register_prompt("KEY_B", "b v1")
        a2 = registry.register_prompt("KEY_A", "a v2")

        assert a1.prompt_version == 1
        assert b1.prompt_version == 1
        assert a2.prompt_version == 2

    def test_hash_computation(self, db: Session) -> None:
        """SHA256 哈希计算正确性"""
        registry = PromptRegistry(db)
        content = "测试内容"
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        template = registry.register_prompt("HASH_KEY", content)

        assert template.prompt_hash == expected_hash

    def test_get_prompt_by_version(self, db: Session) -> None:
        """按版本号获取 Prompt"""
        registry = PromptRegistry(db)
        registry.register_prompt("GET_KEY", "v1 content")
        registry.register_prompt("GET_KEY", "v2 content")

        result = registry.get_prompt("GET_KEY", version=2)
        assert result is not None
        assert result.content == "v2 content"
        assert result.prompt_version == 2

    def test_get_prompt_default_version(self, db: Session) -> None:
        """获取默认版本 Prompt"""
        registry = PromptRegistry(db)
        v1 = registry.register_prompt("DEF_KEY", "default content")
        registry.register_prompt("DEF_KEY", "new content")

        result = registry.get_prompt("DEF_KEY")
        assert result is not None
        assert result.prompt_version == 1
        assert result.is_default is True

    def test_get_prompt_not_found(self, db: Session) -> None:
        """获取不存在的 Prompt 返回 None"""
        registry = PromptRegistry(db)
        result = registry.get_prompt("NONEXISTENT_KEY")
        assert result is None

    def test_set_default(self, db: Session) -> None:
        """切换默认版本"""
        registry = PromptRegistry(db)
        v1 = registry.register_prompt("SWITCH_KEY", "v1")
        v2 = registry.register_prompt("SWITCH_KEY", "v2")
        v3 = registry.register_prompt("SWITCH_KEY", "v3")

        # v1 默认
        assert v1.is_default is True

        # 切换到 v2
        result = registry.set_default("SWITCH_KEY", 2)
        assert result.prompt_version == 2
        assert result.is_default is True

        # v1 不再是默认
        db.refresh(v1)
        assert v1.is_default is False

        # 切换到 v3
        result = registry.set_default("SWITCH_KEY", 3)
        assert result.is_default is True

        # v2 不再是默认
        db.refresh(v2)
        assert v2.is_default is False

    def test_set_default_nonexistent_version(self, db: Session) -> None:
        """切换不存在的版本时抛出 ValueError"""
        registry = PromptRegistry(db)
        registry.register_prompt("MISS_KEY", "only v1")

        with pytest.raises(ValueError, match="不存在"):
            registry.set_default("MISS_KEY", 99)

    def test_rollback(self, db: Session) -> None:
        """回滚到指定版本：设为默认并禁用更高版本"""
        registry = PromptRegistry(db)
        v1 = registry.register_prompt("ROLL_KEY", "v1")
        v2 = registry.register_prompt("ROLL_KEY", "v2")
        v3 = registry.register_prompt("ROLL_KEY", "v3")

        # 先切换默认到 v3
        registry.set_default("ROLL_KEY", 3)

        # 回滚到 v1
        result = registry.rollback("ROLL_KEY", 1)
        assert result.prompt_version == 1
        assert result.is_default is True
        assert result.enabled is True

        # v2 和 v3 被禁用
        db.refresh(v2)
        db.refresh(v3)
        assert v2.enabled is False
        assert v3.enabled is False

    def test_rollback_nonexistent_version(self, db: Session) -> None:
        """回滚到不存在的版本时抛出 ValueError"""
        registry = PromptRegistry(db)
        registry.register_prompt("ROLL_MISS_KEY", "v1")

        with pytest.raises(ValueError, match="不存在"):
            registry.rollback("ROLL_MISS_KEY", 99)

    def test_list_versions(self, db: Session) -> None:
        """列出所有版本，按版本号升序"""
        registry = PromptRegistry(db)
        registry.register_prompt("LIST_KEY", "v1")
        registry.register_prompt("LIST_KEY", "v2")
        registry.register_prompt("LIST_KEY", "v3")

        versions = registry.list_versions("LIST_KEY")
        assert len(versions) == 3
        assert [v.prompt_version for v in versions] == [1, 2, 3]

    def test_list_versions_empty(self, db: Session) -> None:
        """列出不存在 key 的版本返回空列表"""
        registry = PromptRegistry(db)
        versions = registry.list_versions("EMPTY_KEY")
        assert versions == []

    def test_get_prompt_content_from_db(self, db: Session) -> None:
        """从 DB 获取 Prompt 内容"""
        registry = PromptRegistry(db)
        registry.register_prompt("CONTENT_KEY", "db content")

        content = registry.get_prompt_content("CONTENT_KEY")
        assert content == "db content"

    def test_get_prompt_content_fallback_to_hardcoded(self, db: Session) -> None:
        """DB 无记录时 fallback 到硬编码常量"""
        # 注册硬编码 fallback
        register_hardcoded_prompt("FALLBACK_KEY", "hardcoded content")

        registry = PromptRegistry(db)
        content = registry.get_prompt_content("FALLBACK_KEY")
        assert content == "hardcoded content"

    def test_get_prompt_content_empty_when_no_fallback(self, db: Session) -> None:
        """DB 无记录且无硬编码 fallback 时返回空字符串"""
        registry = PromptRegistry(db)
        content = registry.get_prompt_content("NO_FALLBACK_KEY")
        assert content == ""

    def test_get_prompt_content_db_takes_priority(self, db: Session) -> None:
        """DB 记录优先于硬编码 fallback"""
        register_hardcoded_prompt("PRIORITY_KEY", "hardcoded")
        registry = PromptRegistry(db)
        registry.register_prompt("PRIORITY_KEY", "db version")

        content = registry.get_prompt_content("PRIORITY_KEY")
        assert content == "db version"

    def test_get_prompt_disabled_version_excluded(self, db: Session) -> None:
        """get_prompt 不返回被禁用的版本"""
        registry = PromptRegistry(db)
        v1 = registry.register_prompt("DISABLED_KEY", "v1")
        v2 = registry.register_prompt("DISABLED_KEY", "v2")

        # 回滚到 v1，禁用 v2
        registry.rollback("DISABLED_KEY", 1)

        # 按版本号获取被禁用的版本返回 None
        result = registry.get_prompt("DISABLED_KEY", version=2)
        assert result is None

        # 获取默认版本正常
        result = registry.get_prompt("DISABLED_KEY")
        assert result is not None
        assert result.prompt_version == 1

    def test_rollback_re_enables_target(self, db: Session) -> None:
        """回滚时确保目标版本被启用"""
        registry = PromptRegistry(db)
        registry.register_prompt("REENABLE_KEY", "v1")
        registry.register_prompt("REENABLE_KEY", "v2")

        # 先回滚到 v1（禁用 v2）
        registry.rollback("REENABLE_KEY", 1)

        # 再注册 v3
        v3 = registry.register_prompt("REENABLE_KEY", "v3")

        # 再回滚到 v1（禁用 v2 和 v3）
        result = registry.rollback("REENABLE_KEY", 1)
        assert result.enabled is True
        assert result.is_default is True

        db.refresh(v3)
        assert v3.enabled is False
