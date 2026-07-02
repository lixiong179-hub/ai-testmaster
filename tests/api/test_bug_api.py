"""Bug缺陷列表 API 测试（async endpoint）

覆盖场景:
    - 空列表、单条/多条列表
    - 项目不存在 404
    - ux_category 非法 400
    - severity / source / status / ux_category 单维度筛选
    - 多维度组合筛选
    - 分页（page / page_size）
    - 排序（create_time desc）
    - 未认证 401

测试 fixture 由 tests/api/conftest.py 提供（async_db / async_auth_client / async_test_project）。
"""
import pytest

from app.models.bug import Bug
from app.models.project import Project


async def _create_bug(
    db,
    project_id: int,
    reporter_id: int,
    *,
    bug_no: str,
    title: str = "测试Bug",
    severity: int = 3,
    priority: int = 2,
    status: str = "open",
    source: str = "manual",
    ux_category: str | None = None,
) -> Bug:
    """辅助：在 async_db 中创建一条 Bug 记录。"""
    bug = Bug(
        bug_no=bug_no,
        project_id=project_id,
        title=title,
        description=f"{title} 详情",
        severity=severity,
        priority=priority,
        status=status,
        source=source,
        ux_category=ux_category,
        reporter_id=reporter_id,
    )
    db.add(bug)
    await db.flush()
    return bug


class TestBugListAsyncAPI:
    """Bug列表端点 async 测试"""

    async def test_list_empty(self, async_auth_client, async_test_project):
        """项目存在但无 Bug，返回空列表"""
        resp = await async_auth_client.get(
            "/api/v1/bugs/list", params={"project_id": async_test_project.id}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    async def test_list_project_not_found(self, async_auth_client):
        """项目不存在返回 404"""
        resp = await async_auth_client.get(
            "/api/v1/bugs/list", params={"project_id": 999999}
        )
        assert resp.status_code == 404
        assert "项目不存在" in resp.text

    async def test_list_invalid_ux_category(
        self, async_auth_client, async_test_project
    ):
        """ux_category 非法返回 400"""
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "ux_category": "invalid_cat"},
        )
        assert resp.status_code == 400
        assert "ux_category 不合法" in resp.text

    async def test_list_single_bug(self, async_auth_client, async_db, async_test_project, async_test_user):
        """单条 Bug 列表"""
        await _create_bug(
            async_db,
            project_id=async_test_project.id,
            reporter_id=async_test_user.id,
            bug_no="BUG-001",
            title="单条Bug",
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list", params={"project_id": async_test_project.id}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-001"
        assert data["items"][0]["title"] == "单条Bug"

    async def test_list_filter_by_severity(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 severity 筛选"""
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-S1", severity=1,
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-S3", severity=3,
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "severity": 1},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-S1"

    async def test_list_filter_by_source(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 source 筛选"""
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-MAN", source="manual",
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-SELF", source="self_test",
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "source": "self_test"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-SELF"

    async def test_list_filter_by_status(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 status 筛选"""
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-OPEN", status="open",
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-FIXED", status="fixed",
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "status": "fixed"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-FIXED"

    async def test_list_filter_by_ux_category(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 ux_category 筛选"""
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-UX1", ux_category="loading_experience",
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-UX2", ux_category="error_feedback",
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={
                "project_id": async_test_project.id,
                "ux_category": "loading_experience",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-UX1"

    async def test_list_combined_filters(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """多维度组合筛选"""
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-C1", severity=2, source="manual",
            status="open", ux_category="visual_consistency",
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-C2", severity=2, source="self_test",
            status="open", ux_category="visual_consistency",
        )
        await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-C3", severity=2, source="manual",
            status="fixed", ux_category="visual_consistency",
        )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={
                "project_id": async_test_project.id,
                "severity": 2,
                "source": "manual",
                "status": "open",
                "ux_category": "visual_consistency",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-C1"

    async def test_list_pagination(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """分页：page_size=2, page=2 返回第2页"""
        for i in range(5):
            await _create_bug(
                async_db, async_test_project.id, async_test_user.id,
                bug_no=f"BUG-P{i}",
            )
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={
                "project_id": async_test_project.id,
                "page": 2,
                "page_size": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 5
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert len(data["items"]) == 2

    async def test_list_order_by_create_time_desc(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """列表按 create_time 倒序返回"""
        bug_a = await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-A",
        )
        bug_b = await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-B",
        )
        bug_c = await _create_bug(
            async_db, async_test_project.id, async_test_user.id,
            bug_no="BUG-C",
        )
        # 显式设置 create_time 让排序可测（_create_bug 用 default=utcnow）
        from datetime import datetime, timezone, timedelta
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bug_a.create_time = base
        bug_b.create_time = base + timedelta(days=1)
        bug_c.create_time = base + timedelta(days=2)
        await async_db.flush()

        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "page_size": 10},
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 3
        # 倒序：C → B → A
        assert items[0]["bug_no"] == "BUG-C"
        assert items[1]["bug_no"] == "BUG-B"
        assert items[2]["bug_no"] == "BUG-A"

    async def test_unauthenticated(self, async_client, async_test_project):
        """未认证访问返回 401"""
        resp = await async_client.get(
            "/api/v1/bugs/list", params={"project_id": async_test_project.id}
        )
        assert resp.status_code in (401, 403)

    async def test_list_severity_out_of_range(
        self, async_auth_client, async_test_project
    ):
        """severity 超出 1-4 范围返回 400（全局 RequestValidationError 处理器统一为 400）"""
        resp = await async_auth_client.get(
            "/api/v1/bugs/list",
            params={"project_id": async_test_project.id, "severity": 5},
        )
        assert resp.status_code == 400

    async def test_list_only_returns_project_bugs(
        self, async_auth_client, async_db, async_test_user
    ):
        """只返回指定项目的 Bug，不跨项目"""
        # 项目1
        proj1 = Project(
            name="proj1", user_id=async_test_user.id, description="p1",
            status=1, project_type="web",
        )
        async_db.add(proj1)
        await async_db.flush()
        # 项目2
        proj2 = Project(
            name="proj2", user_id=async_test_user.id, description="p2",
            status=1, project_type="web",
        )
        async_db.add(proj2)
        await async_db.flush()

        await _create_bug(
            async_db, proj1.id, async_test_user.id, bug_no="BUG-P1",
        )
        await _create_bug(
            async_db, proj2.id, async_test_user.id, bug_no="BUG-P2",
        )

        resp = await async_auth_client.get(
            "/api/v1/bugs/list", params={"project_id": proj1.id}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["bug_no"] == "BUG-P1"
