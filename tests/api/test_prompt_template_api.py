"""Prompt 模板版本管理端点 async 测试。

覆盖 4 个端点的正常/异常/边界/权限场景。
使用 tests/api/conftest.py 的 async_db / async_client / async_auth_client / async_admin_client fixture。
"""
import hashlib

import pytest_asyncio
from sqlalchemy import select

from app.models.prompt_template import PromptTemplate


def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _create_template(
    db,
    *,
    key: str = "TEST_KEY",
    content: str = "test content",
    version: int = 1,
    is_default: bool = False,
    enabled: bool = True,
    description: str | None = None,
) -> PromptTemplate:
    template = PromptTemplate(
        prompt_key=key,
        prompt_version=version,
        prompt_hash=_compute_hash(content),
        content=content,
        enabled=enabled,
        is_default=is_default,
        description=description,
    )
    db.add(template)
    await db.flush()
    return template


class TestListPromptTemplates:
    """GET /api/v1/prompt-templates/ 列表查询。"""

    async def test_list_empty(self, async_auth_client) -> None:
        resp = await async_auth_client.get("/api/v1/prompt-templates/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    async def test_list_single(self, async_db, async_auth_client) -> None:
        await _create_template(async_db, key="SINGLE", content="c1", is_default=True)
        resp = await async_auth_client.get("/api/v1/prompt-templates/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["prompt_key"] == "SINGLE"

    async def test_list_filter_by_key(self, async_db, async_auth_client) -> None:
        await _create_template(async_db, key="KEY_A", content="a", version=1)
        await _create_template(async_db, key="KEY_B", content="b", version=1)
        resp = await async_auth_client.get(
            "/api/v1/prompt-templates/", params={"prompt_key": "KEY_A"}
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["prompt_key"] == "KEY_A"

    async def test_list_ordering(self, async_db, async_auth_client) -> None:
        await _create_template(async_db, key="ORD", content="c2", version=2)
        await _create_template(async_db, key="ORD", content="c1", version=1)
        resp = await async_auth_client.get(
            "/api/v1/prompt-templates/", params={"prompt_key": "ORD"}
        )
        assert resp.status_code == 200
        versions = [item["prompt_version"] for item in resp.json()["items"]]
        assert versions == [1, 2]


class TestRegisterPromptTemplate:
    """POST /api/v1/prompt-templates/ 注册新版本。"""

    async def test_register_first_version_is_default(
        self, async_admin_client
    ) -> None:
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/",
            json={"prompt_key": "NEW_KEY", "content": "first content"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["prompt_key"] == "NEW_KEY"
        assert body["prompt_version"] == 1
        assert body["is_default"] is True
        assert body["enabled"] is True

    async def test_register_auto_increment(
        self, async_db, async_admin_client
    ) -> None:
        await _create_template(async_db, key="INC", content="v1", version=1, is_default=True)
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/",
            json={"prompt_key": "INC", "content": "v2 different"},
        )
        assert resp.status_code == 201
        assert resp.json()["prompt_version"] == 2
        assert resp.json()["is_default"] is False

    async def test_register_duplicate_content_rejected(
        self, async_db, async_admin_client
    ) -> None:
        await _create_template(async_db, key="DUP", content="same", version=1, is_default=True)
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/",
            json={"prompt_key": "DUP", "content": "same"},
        )
        assert resp.status_code == 409
        assert "完全相同" in resp.json()["msg"]

    async def test_register_empty_content_validation(
        self, async_admin_client
    ) -> None:
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/",
            json={"prompt_key": "VAL", "content": ""},
        )
        assert resp.status_code == 400


class TestSetDefaultPrompt:
    """POST /api/v1/prompt-templates/{key}/set-default 设为默认。"""

    async def test_set_default_switches(self, async_db, async_admin_client) -> None:
        await _create_template(async_db, key="SD", content="v1", version=1, is_default=True)
        await _create_template(async_db, key="SD", content="v2", version=2, is_default=False)
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/SD/set-default",
            json={"version": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["prompt_version"] == 2
        assert resp.json()["is_default"] is True
        stmt = select(PromptTemplate).where(
            PromptTemplate.prompt_key == "SD",
            PromptTemplate.prompt_version == 1,
        )
        old_default = (await async_db.execute(stmt)).scalar_one()
        await async_db.refresh(old_default)
        assert old_default.is_default is False

    async def test_set_default_not_found(self, async_admin_client) -> None:
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/NONEXIST/set-default",
            json={"version": 1},
        )
        assert resp.status_code == 404

    async def test_set_default_invalid_version_zero(
        self, async_admin_client
    ) -> None:
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/ANY/set-default",
            json={"version": 0},
        )
        assert resp.status_code == 400


class TestRollbackPrompt:
    """POST /api/v1/prompt-templates/{key}/rollback 回滚。"""

    async def test_rollback_disables_higher_versions(
        self, async_db, async_admin_client
    ) -> None:
        await _create_template(async_db, key="RB", content="v1", version=1)
        await _create_template(async_db, key="RB", content="v2", version=2, is_default=True)
        await _create_template(async_db, key="RB", content="v3", version=3)
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/RB/rollback",
            json={"target_version": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["prompt_version"] == 1
        assert resp.json()["is_default"] is True
        assert resp.json()["enabled"] is True

        stmt_v2 = select(PromptTemplate).where(
            PromptTemplate.prompt_key == "RB",
            PromptTemplate.prompt_version == 2,
        )
        v2 = (await async_db.execute(stmt_v2)).scalar_one()
        await async_db.refresh(v2)
        assert v2.enabled is False
        assert v2.is_default is False

    async def test_rollback_not_found(self, async_admin_client) -> None:
        resp = await async_admin_client.post(
            "/api/v1/prompt-templates/NONEXIST/rollback",
            json={"target_version": 1},
        )
        assert resp.status_code == 404


class TestPromptTemplatePermissions:
    """权限测试：未认证 401 / 普通用户 403 / admin 正常。"""

    async def test_list_unauthorized(self, async_client) -> None:
        resp = await async_client.get("/api/v1/prompt-templates/")
        assert resp.status_code in (401, 403)

    async def test_register_forbidden_for_normal_user(
        self, async_auth_client
    ) -> None:
        resp = await async_auth_client.post(
            "/api/v1/prompt-templates/",
            json={"prompt_key": "FORBIDDEN", "content": "x"},
        )
        assert resp.status_code == 403

    async def test_set_default_forbidden_for_normal_user(
        self, async_auth_client
    ) -> None:
        resp = await async_auth_client.post(
            "/api/v1/prompt-templates/ANY/set-default",
            json={"version": 1},
        )
        assert resp.status_code == 403

    async def test_rollback_forbidden_for_normal_user(
        self, async_auth_client
    ) -> None:
        resp = await async_auth_client.post(
            "/api/v1/prompt-templates/ANY/rollback",
            json={"target_version": 1},
        )
        assert resp.status_code == 403
