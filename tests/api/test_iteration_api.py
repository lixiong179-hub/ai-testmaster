"""iteration 端点 async 测试。

覆盖 /api/v1/iteration/ 下的创建、列表、详情、更新、删除、定稿端点。
使用 tests/api/conftest.py 的 async fixture。
"""
from app.crud import iteration as iteration_crud


async def _create_iteration(async_db, project_id, name="测试迭代"):
    """通过 run_sync 调用 sync crud 创建迭代。"""
    def _create(sync_db):
        return iteration_crud.create_iteration(db=sync_db, project_id=project_id, name=name)
    return await async_db.run_sync(_create)


class TestCreateIterationAPI:

    async def test_create_success(self, async_auth_client, async_test_project):
        payload = {
            "project_id": async_test_project.id,
            "name": "API创建迭代",
            "version": "v1.0",
        }
        response = await async_auth_client.post(
            "/api/v1/iteration/",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "API创建迭代"
        assert data["status"] == "draft"

    async def test_create_duplicate_name(self, async_auth_client, async_test_project):
        payload = {
            "project_id": async_test_project.id,
            "name": "重复迭代名",
        }
        await async_auth_client.post("/api/v1/iteration/", json=payload)
        response = await async_auth_client.post("/api/v1/iteration/", json=payload)
        assert response.status_code == 400

    async def test_create_without_project_permission(self, async_auth_client):
        payload = {
            "project_id": 99999,
            "name": "无权限迭代",
        }
        response = await async_auth_client.post("/api/v1/iteration/", json=payload)
        assert response.status_code == 403

    async def test_create_unauthenticated(self, async_client, async_test_project):
        payload = {
            "project_id": async_test_project.id,
            "name": "未认证迭代",
        }
        response = await async_client.post("/api/v1/iteration/", json=payload)
        assert response.status_code == 401


class TestGetIterationsAPI:

    async def test_list_iterations(self, async_auth_client, async_db, async_test_project):
        await _create_iteration(async_db, async_test_project.id, "列表迭代")
        response = await async_auth_client.get(
            f"/api/v1/iteration/list/{async_test_project.id}",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "items" in data
        assert "total" in data

    async def test_list_unauthenticated(self, async_client, async_test_project):
        response = await async_client.get(f"/api/v1/iteration/list/{async_test_project.id}")
        assert response.status_code == 401

    async def test_list_no_permission(self, async_auth_client):
        response = await async_auth_client.get("/api/v1/iteration/list/99999")
        assert response.status_code == 403


class TestGetIterationDetailAPI:

    async def test_get_detail(self, async_auth_client, async_db, async_test_project):
        iteration = await _create_iteration(async_db, async_test_project.id, "详情迭代")
        response = await async_auth_client.get(
            f"/api/v1/iteration/{iteration.id}",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "详情迭代"

    async def test_get_nonexistent(self, async_auth_client):
        response = await async_auth_client.get("/api/v1/iteration/99999")
        assert response.status_code == 404


class TestUpdateIterationAPI:

    async def test_update_name(self, async_auth_client, async_db, async_test_project):
        iteration = await _create_iteration(async_db, async_test_project.id, "更新前")
        response = await async_auth_client.put(
            f"/api/v1/iteration/{iteration.id}",
            json={"name": "更新后"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "更新后"

    async def test_update_status_to_in_pipeline(self, async_auth_client, async_db, async_test_project):
        iteration = await _create_iteration(async_db, async_test_project.id, "状态测试")
        response = await async_auth_client.put(
            f"/api/v1/iteration/{iteration.id}",
            json={"status": "in_pipeline"},
        )
        assert response.status_code == 200

    async def test_update_nonexistent(self, async_auth_client):
        response = await async_auth_client.put(
            "/api/v1/iteration/99999",
            json={"name": "不存在"},
        )
        assert response.status_code == 404


class TestDeleteIterationAPI:

    async def test_delete_success(self, async_auth_client, async_db, async_test_project):
        iteration = await _create_iteration(async_db, async_test_project.id, "删除迭代")
        response = await async_auth_client.delete(
            f"/api/v1/iteration/{iteration.id}",
        )
        assert response.status_code == 200

    async def test_delete_nonexistent(self, async_auth_client):
        response = await async_auth_client.delete("/api/v1/iteration/99999")
        assert response.status_code == 404


class TestFinalizeIterationAPI:

    async def test_finalize_wrong_status(self, async_auth_client, async_db, async_test_project):
        iteration = await _create_iteration(async_db, async_test_project.id, "定稿测试")
        response = await async_auth_client.post(
            f"/api/v1/iteration/{iteration.id}/finalize",
        )
        assert response.status_code == 400

    async def test_finalize_nonexistent(self, async_auth_client):
        response = await async_auth_client.post("/api/v1/iteration/99999/finalize")
        assert response.status_code == 404
