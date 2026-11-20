"""单个 API 前置调用行为护栏（G-8 B4m：`_execute_single_api_call` 拆分前置测试）。

覆盖 URL 安全闸门、body 变量替换与请求体装载、headers 透传、
状态码断言、变量提取、超时/连接失败/未知异常三类降级。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.services.test_execution_engine.api_setup_mixin._executor import _ExecutorMixin


class _ApiHarness(_ExecutorMixin):
    """最小宿主：URL 安全 / 变量替换 / 变量提取均可打桩。"""

    def __init__(self, safe_url: bool = True) -> None:
        self._api_extracted_vars: dict[str, Any] = {}
        self._safe_url = safe_url
        self.substituted: list[dict] = []
        self.extracted: list[tuple] = []

    async def _is_safe_url(self, url: str) -> bool:
        return self._safe_url

    def _substitute_api_vars(self, data: dict[str, Any]) -> dict[str, Any]:
        self.substituted.append(data)
        return {key: f"sub-{value}" for key, value in data.items()}

    def _extract_api_vars(self, response, extract_config: dict[str, Any]) -> None:
        self.extracted.append((response, extract_config))


def _client(response: Any = None, error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    if error is not None:
        client.request = AsyncMock(side_effect=error)
    else:
        client.request = AsyncMock(return_value=response)
    return client


def _response(status_code: int = 200, text: str = "ok") -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return response


class TestRequestBuilding:
    async def test_unsafe_url_blocks_request(self):
        engine = _ApiHarness(safe_url=False)
        client = _client(_response())

        ok = await engine._execute_single_api_call(client, {"method": "GET", "url": "http://127.0.0.1"}, 1)

        assert ok is False
        client.request.assert_not_awaited()

    async def test_post_body_substituted_and_sent_as_json(self):
        engine = _ApiHarness()
        client = _client(_response())

        ok = await engine._execute_single_api_call(
            client,
            {"method": "post", "url": "/api/login", "body": {"user": "{{name}}"}},
            1,
        )

        assert ok is True
        assert engine.substituted == [{"user": "{{name}}"}]
        client.request.assert_awaited_once_with("POST", "/api/login", json={"user": "sub-{{name}}"})

    async def test_get_body_not_sent_as_json(self):
        engine = _ApiHarness()
        client = _client(_response())

        await engine._execute_single_api_call(client, {"method": "GET", "url": "/api/list", "body": {"a": 1}}, 1)

        client.request.assert_awaited_once_with("GET", "/api/list")

    async def test_headers_passed_through(self):
        engine = _ApiHarness()
        client = _client(_response())

        await engine._execute_single_api_call(
            client,
            {"method": "GET", "url": "/api/list", "headers": {"X-Token": "abc"}},
            1,
        )

        client.request.assert_awaited_once_with("GET", "/api/list", headers={"X-Token": "abc"})

    async def test_default_method_is_get(self):
        engine = _ApiHarness()
        client = _client(_response())

        await engine._execute_single_api_call(client, {"url": "/api/ping"}, 1)

        assert client.request.await_args.args[0] == "GET"


class TestAssertionAndExtraction:
    async def test_status_mismatch_fails(self):
        engine = _ApiHarness()
        client = _client(_response(status_code=500))

        ok = await engine._execute_single_api_call(
            client,
            {"method": "GET", "url": "/api/x", "assert": {"status_code": 200}},
            1,
        )

        assert ok is False

    async def test_status_match_extracts_vars(self):
        engine = _ApiHarness()
        response = _response(status_code=201)
        client = _client(response)

        ok = await engine._execute_single_api_call(
            client,
            {
                "method": "POST",
                "url": "/api/x",
                "body": {"a": 1},
                "assert": {"status_code": 201},
                "extract": {"token": "$.data.token"},
            },
            1,
        )

        assert ok is True
        assert engine.extracted == [(response, {"token": "$.data.token"})]


class TestFailureDegradation:
    async def test_timeout_returns_false(self):
        engine = _ApiHarness()
        client = _client(error=httpx.TimeoutException("timeout"))

        assert await engine._execute_single_api_call(client, {"method": "GET", "url": "/api/x"}, 1) is False

    async def test_connect_error_returns_false(self):
        engine = _ApiHarness()
        client = _client(error=httpx.ConnectError("refused"))

        assert await engine._execute_single_api_call(client, {"method": "GET", "url": "/api/x"}, 1) is False

    async def test_unexpected_exception_returns_false(self):
        engine = _ApiHarness()
        client = _client(error=ValueError("boom"))

        assert await engine._execute_single_api_call(client, {"method": "GET", "url": "/api/x"}, 1) is False
