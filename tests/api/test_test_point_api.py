"""测试点端点 async 测试。

覆盖 /api/v1/test-point/ 端点的列表、详情、批量保存、更新、删除场景。
使用 tests/api/conftest.py 的 async fixture。
"""
import pytest
from app.models.test_point import TestPoint


class TestTestPointList:
    async def test_list_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/test-point/list/{async_test_project.id}",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    async def test_list_with_data(self, async_auth_client, async_db, async_test_project):
        tp = TestPoint(
            project_id=async_test_project.id,
            module="列表模块",
            point="列表测试点",
            priority=1,
        )
        async_db.add(tp)
        await async_db.flush()
        resp = await async_auth_client.get(
            f"/api/v1/test-point/list/{async_test_project.id}",
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    async def test_list_with_filters(self, async_auth_client, async_db, async_test_project):
        tp = TestPoint(
            project_id=async_test_project.id,
            module="过滤模块",
            point="过滤测试点",
            priority=1,
        )
        async_db.add(tp)
        await async_db.flush()
        resp = await async_auth_client.get(
            f"/api/v1/test-point/list/{async_test_project.id}",
            params={"module": "过滤模块", "priority": 1},
        )
        assert resp.status_code == 200

    async def test_list_pagination(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/test-point/list/{async_test_project.id}",
            params={"page": 1, "page_size": 5},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 5


class TestTestPointDetail:
    async def test_get_existing(self, async_auth_client, async_db, async_test_project):
        tp = TestPoint(
            project_id=async_test_project.id,
            module="详情模块",
            point="详情测试点",
            priority=2,
        )
        async_db.add(tp)
        await async_db.flush()
        resp = await async_auth_client.get(
            f"/api/v1/test-point/detail/{tp.id}",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code == 200

    async def test_get_nonexistent(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            "/api/v1/test-point/detail/99999",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code == 404


class TestTestPointBatchSave:
    async def test_batch_save_normal(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": async_test_project.id},
            json=[
                {"module": "批量模块1", "point": "批量点1", "priority": 1},
                {"module": "批量模块2", "point": "批量点2", "priority": 2},
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["saved_count"] == 2

    async def test_batch_save_empty_list(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": async_test_project.id},
            json=[],
        )
        assert resp.status_code == 400

    async def test_batch_save_invalid_items(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": async_test_project.id},
            json=[
                {"module": "", "point": "", "priority": 2},
            ],
        )
        assert resp.status_code == 400

    async def test_batch_save_too_many(self, async_auth_client, async_test_project):
        points = [{"module": f"M{i}", "point": f"P{i}", "priority": 2} for i in range(201)]
        resp = await async_auth_client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": async_test_project.id},
            json=points,
        )
        assert resp.status_code == 400


class TestTestPointUpdate:
    async def test_update_normal(self, async_auth_client, async_db, async_test_project):
        tp = TestPoint(
            project_id=async_test_project.id,
            module="更新前",
            point="更新测试点",
            priority=2,
        )
        async_db.add(tp)
        await async_db.flush()
        resp = await async_auth_client.put(
            f"/api/v1/test-point/{tp.id}",
            params={"project_id": async_test_project.id},
            json={"module": "更新后", "priority": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["module"] == "更新后"

    async def test_update_nonexistent(self, async_auth_client, async_test_project):
        resp = await async_auth_client.put(
            "/api/v1/test-point/99999",
            params={"project_id": async_test_project.id},
            json={"module": "新模块"},
        )
        assert resp.status_code == 404


class TestTestPointDelete:
    async def test_delete_single(self, async_auth_client, async_db, async_test_project):
        tp = TestPoint(
            project_id=async_test_project.id,
            module="删除模块",
            point="删除测试点",
            priority=2,
        )
        async_db.add(tp)
        await async_db.flush()
        resp = await async_auth_client.delete(
            f"/api/v1/test-point/{tp.id}",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code == 200

    async def test_batch_delete(self, async_auth_client, async_db, async_test_project):
        tp1 = TestPoint(project_id=async_test_project.id, module="BD1", point="P1", priority=2)
        tp2 = TestPoint(project_id=async_test_project.id, module="BD2", point="P2", priority=2)
        async_db.add_all([tp1, tp2])
        await async_db.flush()
        resp = await async_auth_client.request(
            "DELETE",
            "/api/v1/test-point/batch",
            params={"project_id": async_test_project.id},
            json=[tp1.id, tp2.id],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["deleted_count"] >= 1

    async def test_batch_delete_empty_ids(self, async_auth_client, async_test_project):
        resp = await async_auth_client.request(
            "DELETE",
            "/api/v1/test-point/batch",
            params={"project_id": async_test_project.id},
            json=[],
        )
        assert resp.status_code == 400


class TestTestPointNoAuth:
    async def test_list_without_auth(self, async_client, async_test_project):
        resp = await async_client.get(f"/api/v1/test-point/list/{async_test_project.id}")
        assert resp.status_code in (401, 403)
