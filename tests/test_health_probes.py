"""K8s 健康探针端点测试。

覆盖：
    - GET /live：进程存活即 200，不检查依赖
    - GET /ready：依赖就绪 200，否则 503
    - GET /health：完整健康检查（原有端点回归）

设计说明：
    - 使用项目已有 `client` fixture（基于 TestClient + 真实 app）
    - 通过 mock 控制依赖检查结果，验证不同状态响应
    - 真实 DB/Redis 由 conftest.py 提供，无需 mock
"""
from unittest import mock

import pytest


class TestLivenessProbe:
    """/live 端点测试。"""

    def test_live_returns_200(self, client):
        """进程存活即返回 200。"""
        resp = client.get("/live")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "alive"

    def test_live_does_not_check_dependencies(self, client):
        """live 不检查依赖，即使依赖不可用也返回 200。"""
        with mock.patch("app.db.database.check_db_connection", return_value=False):
            resp = client.get("/live")
            assert resp.status_code == 200
            assert resp.json()["status"] == "alive"


class TestReadinessProbe:
    """/ready 端点测试。"""

    def test_ready_returns_200_when_deps_ok(self, client):
        """依赖就绪时返回 200。"""
        with mock.patch("app.db.database.check_db_connection", return_value=True), \
                mock.patch("redis.from_url") as mock_redis:
            mock_r = mock.MagicMock()
            mock_redis.return_value = mock_r
            resp = client.get("/ready")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ready"
            assert body["services"]["database"] is True
            assert body["services"]["redis"] is True

    def test_ready_returns_503_when_db_down(self, client):
        """数据库不可用返回 503。"""
        with mock.patch("app.db.database.check_db_connection", return_value=False), \
                mock.patch("redis.from_url") as mock_redis:
            mock_r = mock.MagicMock()
            mock_redis.return_value = mock_r
            resp = client.get("/ready")
            assert resp.status_code == 503
            # 不披露具体未就绪的依赖，仅返回通用提示
            assert "服务暂不可用" in resp.json()["msg"]

    def test_ready_returns_503_when_redis_down(self, client):
        """Redis 不可用返回 503。"""
        with mock.patch("app.db.database.check_db_connection", return_value=True), \
                mock.patch("redis.from_url", side_effect=Exception("redis down")):
            resp = client.get("/ready")
            assert resp.status_code == 503
            assert "服务暂不可用" in resp.json()["msg"]

    def test_ready_returns_503_when_all_deps_down(self, client):
        """所有依赖不可用返回 503。"""
        with mock.patch("app.db.database.check_db_connection", return_value=False), \
                mock.patch("redis.from_url", side_effect=Exception("redis down")):
            resp = client.get("/ready")
            assert resp.status_code == 503
            # 安全：响应体不披露具体哪些依赖不可用，防止信息探测
            msg = resp.json()["msg"]
            assert "database" not in msg
            assert "redis" not in msg


class TestHealthCheckBackwardCompat:
    """/health 端点回归测试，确保新增 /live /ready 未破坏原端点。"""

    def test_health_returns_200(self, client):
        """原有 /health 端点仍返回 200。"""
        with mock.patch("app.db.database.check_db_connection", return_value=True), \
                mock.patch("redis.from_url") as mock_redis:
            mock_r = mock.MagicMock()
            mock_redis.return_value = mock_r
            resp = client.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] in ("healthy", "degraded")
            assert "version" in body
            assert "services" in body

    def test_health_degraded_when_db_down(self, client):
        """数据库不可用时 health 返回 degraded 状态（仍 200）。"""
        with mock.patch("app.db.database.check_db_connection", return_value=False), \
                mock.patch("redis.from_url") as mock_redis:
            mock_r = mock.MagicMock()
            mock_redis.return_value = mock_r
            resp = client.get("/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "degraded"
            assert body["services"]["database"] == "unhealthy"


class TestProbeEndpointSemantics:
    """探针端点语义正确性测试。"""

    def test_live_is_lightweight(self, client):
        """live 端点不调用依赖检查函数（性能要求）。"""
        with mock.patch("app.db.database.check_db_connection") as mock_db, \
                mock.patch("redis.from_url") as mock_redis:
            client.get("/live")
            mock_db.assert_not_called()
            mock_redis.assert_not_called()

    def test_ready_checks_both_deps(self, client):
        """ready 端点同时检查 DB 和 Redis。"""
        with mock.patch("app.db.database.check_db_connection", return_value=True) as mock_db, \
                mock.patch("redis.from_url") as mock_redis:
            mock_r = mock.MagicMock()
            mock_redis.return_value = mock_r
            client.get("/ready")
            mock_db.assert_called_once()
            mock_redis.assert_called_once()
