"""
Prometheus /metrics 端点集成测试

测试对象: app/main.py 中注册的 Instrumentator().instrument(app).expose(app, endpoint="/metrics")
依赖: 真实 app 实例（通过 tests/conftest.py 的 client fixture 注入，禁止 Mock）
运行: python -m pytest tests/test_metrics_endpoint.py -v --tb=short
"""
import pytest


def test_metrics_endpoint_returns_prometheus_format(client):
    """验证 /metrics 端点返回 Prometheus 文本格式指标

    业务原因: Prometheus 抓取器要求 /metrics 返回标准 exposition format，
    Content-Type 必须为 text/plain，且响应体包含 HTTP 请求指标，
    否则抓取后无法解析，Grafana 面板无数据。
    """
    # 先访问一次业务端点以触发 HTTP 请求指标采集（instrumentator 中间件记录）
    healthResp = client.get("/health")
    assert healthResp.status_code == 200, f"/health 健康检查失败: {healthResp.status_code}"

    # 读取 /metrics 端点
    response = client.get("/metrics")

    # 状态码必须 200（Prometheus 抓取健康检查依赖）
    assert response.status_code == 200, f"/metrics 返回非 200 状态码: {response.status_code}"

    # Content-Type 必须包含 text/plain（Prometheus exposition format 规范）
    contentType = response.headers.get("content-type", "")
    assert "text/plain" in contentType, f"/metrics Content-Type 非 text/plain: {contentType}"

    # 响应体非空
    body = response.text
    assert body.strip(), "/metrics 响应体为空"

    # 必须包含 prometheus-fastapi-instrumentator 默认注册的 HTTP 指标之一
    # http_requests_total: 请求计数器（Counter）
    # http_request_duration_seconds: 请求耗时直方图（Histogram）
    # http_inprogress_requests: 进行中请求（Gauge）
    expectedMetrics = (
        "http_requests_total",
        "http_request_duration_seconds",
        "http_inprogress_requests",
    )
    matchedMetrics = [m for m in expectedMetrics if m in body]
    assert matchedMetrics, (
        f"/metrics 响应未包含任何 Prometheus HTTP 指标，"
        f"期望包含 {expectedMetrics} 之一，实际前 500 字符: {body[:500]}"
    )

    # 验证响应符合 Prometheus exposition format（包含 # HELP 或 # TYPE 注释行）
    assert "# HELP" in body or "# TYPE" in body, (
        f"/metrics 响应未包含 Prometheus 标准注释（# HELP / # TYPE），实际前 500 字符: {body[:500]}"
    )


def test_metrics_endpoint_accessible_without_auth(client):
    """验证 /metrics 端点无需认证即可访问

    业务原因: Prometheus 抓取器不携带业务 JWT，/metrics 必须开放访问，
    否则监控数据无法采集。验证不携带 Authorization 头时返回 200（非 401/403）。
    """
    # 显式不携带任何认证头访问 /metrics（模拟 Prometheus 抓取器行为）
    response = client.get("/metrics")

    # 必须返回 200（非 401 未认证 / 403 禁止访问）
    assert response.status_code == 200, (
        f"/metrics 无认证访问失败，状态码: {response.status_code}（应为 200）"
    )

    # 再次确认响应体有效（非空且为 Prometheus 文本格式）
    body = response.text
    assert body.strip(), "/metrics 无认证访问响应体为空"
    assert "text/plain" in response.headers.get("content-type", ""), (
        f"/metrics 无认证访问 Content-Type 非 text/plain: "
        f"{response.headers.get('content-type', '')}"
    )
