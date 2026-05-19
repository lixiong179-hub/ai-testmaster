import pytest


class TestVisibilityAPI:
    def test_get_global_config(self, client, authHeaders):
        resp = client.get("/api/v1/visibility/config?level=global", headers=authHeaders)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "headless" in data["data"]

    def test_get_task_config_no_id(self, client, authHeaders):
        resp = client.get("/api/v1/visibility/config?level=task", headers=authHeaders)
        assert resp.status_code == 200

    def test_get_case_config_no_id(self, client, authHeaders):
        resp = client.get("/api/v1/visibility/config?level=case", headers=authHeaders)
        assert resp.status_code == 200

    def test_get_unknown_level_defaults_to_global(self, client, authHeaders):
        resp = client.get("/api/v1/visibility/config?level=unknown", headers=authHeaders)
        assert resp.status_code == 200

    def test_update_global_config(self, client, authHeaders):
        resp = client.put(
            "/api/v1/visibility/config",
            json={
                "level": "global",
                "headless": False,
                "record_video": True,
                "execution_speed": "fast",
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["headless"] is False

    def test_update_invalid_config_rejected(self, client, authHeaders):
        resp = client.put(
            "/api/v1/visibility/config",
            json={
                "level": "global",
                "execution_speed": "turbo",
            },
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_update_task_config_not_found(self, client, authHeaders):
        resp = client.put(
            "/api/v1/visibility/config",
            json={
                "level": "task",
                "id": 99999,
                "headless": True,
            },
            headers=authHeaders,
        )
        assert resp.status_code == 404

    def test_update_case_config_not_found(self, client, authHeaders):
        resp = client.put(
            "/api/v1/visibility/config",
            json={
                "level": "case",
                "id": 99999,
                "headless": True,
            },
            headers=authHeaders,
        )
        assert resp.status_code == 404

    def test_unauthenticated_access(self, client):
        resp = client.get("/api/v1/visibility/config?level=global")
        assert resp.status_code in (401, 403)
