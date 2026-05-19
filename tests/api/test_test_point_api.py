import pytest
from app.models.test_point import TestPoint


class TestTestPointList:
    def test_list_empty(self, client, authHeaders, testProject):
        resp = client.get(
            f"/api/v1/test-point/list/{testProject.id}",
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    def test_list_with_data(self, client, db, authHeaders, testProject):
        tp = TestPoint(
            project_id=testProject.id,
            module="列表模块",
            point="列表测试点",
            priority=1,
        )
        db.add(tp)
        db.flush()
        resp = client.get(
            f"/api/v1/test-point/list/{testProject.id}",
            headers=authHeaders,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    def test_list_with_filters(self, client, db, authHeaders, testProject):
        tp = TestPoint(
            project_id=testProject.id,
            module="过滤模块",
            point="过滤测试点",
            priority=1,
        )
        db.add(tp)
        db.flush()
        resp = client.get(
            f"/api/v1/test-point/list/{testProject.id}",
            params={"module": "过滤模块", "priority": 1},
            headers=authHeaders,
        )
        assert resp.status_code == 200

    def test_list_pagination(self, client, authHeaders, testProject):
        resp = client.get(
            f"/api/v1/test-point/list/{testProject.id}",
            params={"page": 1, "page_size": 5},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 5


class TestTestPointDetail:
    def test_get_existing(self, client, db, authHeaders, testProject):
        tp = TestPoint(
            project_id=testProject.id,
            module="详情模块",
            point="详情测试点",
            priority=2,
        )
        db.add(tp)
        db.flush()
        resp = client.get(
            f"/api/v1/test-point/detail/{tp.id}",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert resp.status_code == 200

    def test_get_nonexistent(self, client, authHeaders, testProject):
        resp = client.get(
            "/api/v1/test-point/detail/99999",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert resp.status_code == 404


class TestTestPointBatchSave:
    def test_batch_save_normal(self, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": testProject.id},
            json=[
                {"module": "批量模块1", "point": "批量点1", "priority": 1},
                {"module": "批量模块2", "point": "批量点2", "priority": 2},
            ],
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["saved_count"] == 2

    def test_batch_save_empty_list(self, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": testProject.id},
            json=[],
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_batch_save_invalid_items(self, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": testProject.id},
            json=[
                {"module": "", "point": "", "priority": 2},
            ],
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_batch_save_too_many(self, client, authHeaders, testProject):
        points = [{"module": f"M{i}", "point": f"P{i}", "priority": 2} for i in range(201)]
        resp = client.post(
            "/api/v1/test-point/batch-save",
            params={"project_id": testProject.id},
            json=points,
            headers=authHeaders,
        )
        assert resp.status_code == 400


class TestTestPointUpdate:
    def test_update_normal(self, client, db, authHeaders, testProject):
        tp = TestPoint(
            project_id=testProject.id,
            module="更新前",
            point="更新测试点",
            priority=2,
        )
        db.add(tp)
        db.flush()
        resp = client.put(
            f"/api/v1/test-point/{tp.id}",
            params={"project_id": testProject.id},
            json={"module": "更新后", "priority": 1},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["module"] == "更新后"

    def test_update_nonexistent(self, client, authHeaders, testProject):
        resp = client.put(
            "/api/v1/test-point/99999",
            params={"project_id": testProject.id},
            json={"module": "新模块"},
            headers=authHeaders,
        )
        assert resp.status_code == 404


class TestTestPointDelete:
    def test_delete_single(self, client, db, authHeaders, testProject):
        tp = TestPoint(
            project_id=testProject.id,
            module="删除模块",
            point="删除测试点",
            priority=2,
        )
        db.add(tp)
        db.flush()
        resp = client.delete(
            f"/api/v1/test-point/{tp.id}",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert resp.status_code == 200

    def test_batch_delete(self, client, db, authHeaders, testProject):
        tp1 = TestPoint(project_id=testProject.id, module="BD1", point="P1", priority=2)
        tp2 = TestPoint(project_id=testProject.id, module="BD2", point="P2", priority=2)
        db.add_all([tp1, tp2])
        db.flush()
        resp = client.request(
            "DELETE",
            "/api/v1/test-point/batch",
            params={"project_id": testProject.id},
            json=[tp1.id, tp2.id],
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["deleted_count"] >= 1

    def test_batch_delete_empty_ids(self, client, authHeaders, testProject):
        resp = client.request(
            "DELETE",
            "/api/v1/test-point/batch",
            params={"project_id": testProject.id},
            json=[],
            headers=authHeaders,
        )
        assert resp.status_code == 400


class TestTestPointNoAuth:
    def test_list_without_auth(self, client, testProject):
        resp = client.get(f"/api/v1/test-point/list/{testProject.id}")
        assert resp.status_code in (401, 403)
