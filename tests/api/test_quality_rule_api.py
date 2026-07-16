"""质量规则 API 端点测试（async 试点）。

验证首个 async endpoint 的端到端链路：
    - AsyncSession 依赖注入正确
    - select + await db.execute 查询路径
    - commit + refresh 持久化路径
    - 异常分支（404 项目不存在、401 未认证）

测试 fixture 由 tests/api/conftest.py 提供（async_db / async_client / async_auth_client）。
"""
import pytest


class TestQualityRuleAsyncAPI:
    """质量规则 async endpoint 端到端测试。"""

    async def test_get_rules_unauthenticated_returns_401(self, async_client):
        """未认证访问应返回 401（oauth2_scheme 层拦截，不查 DB）。"""
        resp = await async_client.get("/api/v1/projects/1/quality-rules")
        assert resp.status_code in (401, 403)

    async def test_get_rules_project_not_found_returns_403(
        self, async_auth_client
    ):
        """项目不存在或不属于当前用户均返回 403（不区分以避免泄露存在性）。

        安全收紧：原实现返回 404 暴露项目存在性，现统一返回 403。
        """
        resp = await async_auth_client.get(
            "/api/v1/projects/999999/quality-rules"
        )
        assert resp.status_code == 403
        assert "无权限" in resp.text

    async def test_get_rules_empty_list_returns_200(
        self, async_auth_client, async_test_project
    ):
        """项目无规则时应返回 200 空列表，验证 async select 链路完整。"""
        resp = await async_auth_client.get(
            f"/api/v1/projects/{async_test_project.id}/quality-rules"
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_update_rule_creates_new_rule(
        self, async_auth_client, async_test_project
    ):
        """PUT 不存在的 rule_key 应创建新规则，验证 commit + refresh 路径。"""
        resp = await async_auth_client.put(
            f"/api/v1/projects/{async_test_project.id}/quality-rules",
            json={"rule_key": "title_min", "rule_value": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == async_test_project.id
        assert body["rule_key"] == "title_min"
        assert body["rule_value"] == 10
        # 验证服务器生成的字段已 refresh
        assert body["id"] is not None
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    async def test_update_rule_updates_existing(
        self, async_auth_client, async_test_project
    ):
        """PUT 已存在的 rule_key 应更新值，验证更新 commit 路径。"""
        project_id = async_test_project.id
        # 第一次创建
        resp1 = await async_auth_client.put(
            f"/api/v1/projects/{project_id}/quality-rules",
            json={"rule_key": "steps_min", "rule_value": 3},
        )
        assert resp1.status_code == 200
        # 第二次更新同一 key
        resp2 = await async_auth_client.put(
            f"/api/v1/projects/{project_id}/quality-rules",
            json={"rule_key": "steps_min", "rule_value": 5},
        )
        assert resp2.status_code == 200
        assert resp2.json()["rule_value"] == 5
        assert resp2.json()["id"] == resp1.json()["id"]

    async def test_get_rules_after_update_returns_data(
        self, async_auth_client, async_test_project
    ):
        """创建规则后 GET 应返回该规则，验证持久化到 DB。"""
        project_id = async_test_project.id
        await async_auth_client.put(
            f"/api/v1/projects/{project_id}/quality-rules",
            json={"rule_key": "duplication_threshold", "rule_value": 0.85},
        )
        resp = await async_auth_client.get(
            f"/api/v1/projects/{project_id}/quality-rules"
        )
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) == 1
        assert rules[0]["rule_key"] == "duplication_threshold"
        assert rules[0]["rule_value"] == 0.85

    async def test_update_rule_project_not_found_returns_403(
        self, async_auth_client
    ):
        """PUT 不存在或不属于当前用户的项目应返回 403。"""
        resp = await async_auth_client.put(
            "/api/v1/projects/999999/quality-rules",
            json={"rule_key": "any", "rule_value": 1},
        )
        assert resp.status_code == 403
