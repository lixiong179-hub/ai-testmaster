"""main.py FastAPI 端点测试

覆盖根路径、健康检查、应用工厂各维度场景�?使用真实 TestClient，禁�?Mock�?"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestRootEndpoint:
    def test_root_returns_200(self):
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

    def test_root_returns_json(self):
        client = TestClient(app)
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert "AI TestMaster" in data["message"]
        assert "version" in data


class TestHealthCheck:
    def test_health_returns_200(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_structure(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "services" in data

    def test_health_status_valid_values(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] in ("healthy", "degraded")

    def test_health_services_keys(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert "database" in data["services"]
        assert "redis" in data["services"]
        assert "ai_api" in data["services"]

    def test_health_database_status(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["services"]["database"] in ("healthy", "unhealthy")

    def test_health_ai_api_status(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["services"]["ai_api"] in ("configured", "not_configured")

    def test_health_environment_field(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["environment"] in ("dev", "test", "prod")

    def test_health_version_not_empty(self):
        client = TestClient(app)
        data = client.get("/health").json()
        assert len(data["version"]) > 0
