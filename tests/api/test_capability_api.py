import pytest


class TestCapabilityAPI:
    def test_list_capabilities(self, client, authHeaders, testProject):
        resp = client.get(
            f"/api/v1/test-capability/?project_id={testProject.id}",
            headers=authHeaders,
        )
        assert resp.status_code == 200

    def test_create_capability(self, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "API_TEST_CAP",
                "title": "API测试能力",
                "status": "active",
            },
            headers=authHeaders,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "API_TEST_CAP"

    def test_create_duplicate_capability(self, client, authHeaders, testProject):
        client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "DUP_API_CAP",
                "title": "重复能力",
                "status": "active",
            },
            headers=authHeaders,
        )
        resp = client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "DUP_API_CAP",
                "title": "重复能力2",
                "status": "active",
            },
            headers=authHeaders,
        )
        assert resp.status_code == 409

    def test_get_capability(self, client, authHeaders, testProject):
        create_resp = client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "GET_CAP",
                "title": "查询能力",
                "status": "active",
            },
            headers=authHeaders,
        )
        cap_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/test-capability/{cap_id}", headers=authHeaders)
        assert resp.status_code == 200
        assert resp.json()["key"] == "GET_CAP"

    def test_get_capability_not_found(self, client, authHeaders):
        resp = client.get("/api/v1/test-capability/99999", headers=authHeaders)
        assert resp.status_code == 404

    def test_update_capability(self, client, authHeaders, testProject):
        create_resp = client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "UPD_CAP",
                "title": "更新前",
                "status": "active",
            },
            headers=authHeaders,
        )
        cap_id = create_resp.json()["id"]
        resp = client.put(
            f"/api/v1/test-capability/{cap_id}",
            json={"title": "更新后"},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "更新后"

    def test_delete_capability(self, client, authHeaders, testProject):
        create_resp = client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": testProject.id,
                "key": "DEL_CAP",
                "title": "删除能力",
                "status": "active",
            },
            headers=authHeaders,
        )
        cap_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/test-capability/{cap_id}", headers=authHeaders)
        assert resp.status_code == 204

    def test_delete_capability_not_found(self, client, authHeaders):
        resp = client.delete("/api/v1/test-capability/99999", headers=authHeaders)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, testProject):
        resp = client.get(f"/api/v1/test-capability/?project_id={testProject.id}")
        assert resp.status_code in (401, 403)
