"""B6g 护栏：流式 AI 客户端的 SSE 消费、重试与解析降级路径。"""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.utils.ai_client_core import AIServiceError
from app.utils.ai_client_stream import _analyze as analyze_module
from app.utils.ai_client_stream import _generate as generate_module
from app.utils.ai_client_stream._analyze import _AnalyzeStreamMixin
from app.utils.ai_client_stream._generate import _GenerateStreamMixin


def sse(*deltas: str) -> list[str]:
    """把增量文本拼成标准 SSE 行，并追加 [DONE]。"""
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': delta}}]})}" for delta in deltas]
    return [*lines, "data: [DONE]"]


class FakeSSEResponse:
    def __init__(
        self,
        lines: list[str] | None = None,
        error: Exception | None = None,
        mid_error: Exception | None = None,
    ):
        self.lines = lines or []
        self.error = error
        self.mid_error = mid_error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    async def aiter_lines(self):
        for line in self.lines:
            yield line
        if self.mid_error is not None:
            raise self.mid_error


class FakeStreamContext:
    def __init__(self, response: FakeSSEResponse):
        self.response = response

    async def __aenter__(self) -> FakeSSEResponse:
        return self.response

    async def __aexit__(self, *_exc) -> bool:
        return False


class FakeAsyncClient:
    """按顺序返回预置响应；元素为异常时在 stream() 处抛出。"""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.stream_calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    def stream(self, method, url, headers=None, json=None):
        self.stream_calls.append({"method": method, "url": url, "headers": headers, "json": json})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeStreamContext(item)


def patch_httpx(monkeypatch, module, responses: list) -> FakeAsyncClient:
    client = FakeAsyncClient(responses)
    monkeypatch.setattr(
        module,
        "httpx",
        SimpleNamespace(AsyncClient=lambda **_kwargs: client, HTTPError=httpx.HTTPError),
    )
    return client


def make_generate_mixin(max_retries: int = 1) -> _GenerateStreamMixin:
    mixin = _GenerateStreamMixin()
    mixin.api_key = "test-key"
    mixin.model = "test-model"
    mixin.api_url = "http://test/api"
    mixin.max_retries = max_retries
    mixin.retry_delay = 0
    return mixin


def make_analyze_mixin(max_retries: int = 1) -> _AnalyzeStreamMixin:
    mixin = _AnalyzeStreamMixin()
    mixin.api_key = "test-key"
    mixin.model = "test-model"
    mixin.api_url = "http://test/api"
    mixin.max_retries = max_retries
    mixin.retry_delay = 0
    return mixin


CASE_JSON = json.dumps(
    {
        "title": "登录成功",
        "precondition": "已注册",
        "steps": [{"step": 1, "action": "点击登录"}],
        "expected_result": "进入首页",
        "case_type": "UI",
    },
    ensure_ascii=False,
)


class TestParseStreamTestPoints:
    def setup_method(self):
        self.mixin = make_analyze_mixin()

    def test_direct_json_array(self):
        content = json.dumps([{"module": "M", "point": "P"}])
        assert self.mixin._parse_stream_test_points(content) == [{"module": "M", "point": "P"}]

    def test_fenced_json_block(self):
        content = f"```json\n{json.dumps([{'module': 'M'}])}\n```"
        assert self.mixin._parse_stream_test_points(content) == [{"module": "M"}]

    def test_fenced_json_repaired(self):
        content = '```json\n[{"module": "M", "priority": 1,}]\n```'
        result = self.mixin._parse_stream_test_points(content)
        assert result == [{"module": "M", "priority": 1}]

    def test_bracket_json_in_prose(self):
        content = f"结果如下：[{json.dumps({'module': 'M'})}] 请查收"
        assert self.mixin._parse_stream_test_points(content) == [{"module": "M"}]

    def test_bracket_json_repaired(self):
        content = '结果如下：[{"module": "M",}] 请查收'
        assert self.mixin._parse_stream_test_points(content) == [{"module": "M"}]

    def test_json_object_is_not_accepted_as_array(self):
        result = self.mixin._parse_stream_test_points('{"module": "M", "point": "P"}')

        assert not isinstance(result, dict)

    def test_unrepairable_fenced_block_falls_through(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)

        result = self.mixin._parse_stream_test_points("```json\n[这不是 JSON]\n```")

        assert result is None or isinstance(result, list)

    def test_unparsable_dumps_debug_file(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)

        assert self.mixin._parse_stream_test_points("完全不是 JSON") is None
        assert (tmp_path / "ai_response_debug.txt").read_text(encoding="utf-8") == "完全不是 JSON"

    def test_debug_dump_failure_is_swallowed(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "ai_response_debug.txt").mkdir()

        assert self.mixin._parse_stream_test_points("完全不是 JSON") is None

    def test_fallback_extracts_objects_from_prose(self):
        content = '思考中... [{"module": "M1", "point": "P1"}, {"module": "M2", "point": "P2"}] 以上'

        result = self.mixin._parse_stream_test_points(content)

        assert result is not None
        assert len(result) == 2


class TestGenerateTestCaseStream:
    @pytest.mark.asyncio
    async def test_success_streams_progress_then_data(self, monkeypatch):
        lines = sse(CASE_JSON[:30], CASE_JSON[30:])
        client = patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(lines)])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["progress"] == 100
        assert chunks[-1]["message"] == "生成完成"
        assert chunks[-1]["data"]["title"] == "登录成功"
        assert all("error" not in chunk for chunk in chunks)
        assert len(client.stream_calls) == 1
        assert client.stream_calls[0]["json"]["stream"] is True
        assert client.stream_calls[0]["headers"]["Authorization"] == "Bearer test-key"

    @pytest.mark.asyncio
    async def test_ignores_malformed_and_non_data_lines(self, monkeypatch):
        lines = ["", "event: ping", "data: 不是JSON", 'data: {"no_choices": true}', *sse(CASE_JSON)]
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(lines)])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["data"]["title"] == "登录成功"

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_error(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse(json.dumps({"title": "只有标题"})))])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["status"] == "error"
        assert "缺少必要字段" in chunks[-1]["message"]
        assert "precondition" in chunks[-1]["message"]

    @pytest.mark.asyncio
    async def test_non_object_json_is_format_error(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse('["not", "an", "object"]'))])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["message"] == "AI响应格式错误，无法解析"

    @pytest.mark.asyncio
    async def test_unparsable_content_is_format_error(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse("完全不是 JSON"))])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["message"] == "AI响应格式错误，无法解析"

    @pytest.mark.asyncio
    async def test_fallback_parser_recovers_case(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse(f"好的，用例是：{CASE_JSON} 请查收"))])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["message"] == "生成完成"
        assert chunks[-1]["data"]["title"] == "登录成功"

    @pytest.mark.asyncio
    async def test_http_error_retries_then_succeeds(self, monkeypatch):
        responses = [httpx.ConnectError("boom"), FakeSSEResponse(sse(CASE_JSON))]
        client = patch_httpx(monkeypatch, generate_module, responses)

        chunks = [chunk async for chunk in make_generate_mixin(max_retries=2).generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["data"]["title"] == "登录成功"
        assert len(client.stream_calls) == 2

    @pytest.mark.asyncio
    async def test_mid_stream_failure_does_not_pollute_retry(self, monkeypatch):
        stale_case = json.dumps({**json.loads(CASE_JSON), "title": "上一次残留"}, ensure_ascii=False)
        stale_line = f"data: {json.dumps({'choices': [{'delta': {'content': stale_case}}]}, ensure_ascii=False)}"
        broken = FakeSSEResponse([stale_line], mid_error=httpx.ReadError("断流"))
        client = patch_httpx(monkeypatch, generate_module, [broken, FakeSSEResponse(sse(CASE_JSON))])

        chunks = [chunk async for chunk in make_generate_mixin(max_retries=2).generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["message"] == "生成完成"
        assert chunks[-1]["data"]["title"] == "登录成功"
        assert len(client.stream_calls) == 2

    @pytest.mark.asyncio
    async def test_http_error_exhausted_returns_error(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [httpx.ConnectError("boom")])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["status"] == "error"
        assert chunks[-1]["message"]

    @pytest.mark.asyncio
    async def test_http_status_error_returns_detected_message(self, monkeypatch):
        error = httpx.HTTPStatusError("401", request=httpx.Request("POST", "http://test"), response=httpx.Response(401))
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse(CASE_JSON), error=error)])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["message"]

    @pytest.mark.asyncio
    async def test_service_error_returns_its_message(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [FakeSSEResponse(sse(CASE_JSON), error=AIServiceError("配额不足"))])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["message"] == "配额不足"
        assert chunks[-1]["error"] is True

    @pytest.mark.asyncio
    async def test_unexpected_error_prefixes_message(self, monkeypatch):
        patch_httpx(monkeypatch, generate_module, [ValueError("boom")])

        chunks = [chunk async for chunk in make_generate_mixin().generate_test_case_stream({"point": "P"})]

        assert chunks[-1]["message"].startswith("生成失败: ")


class TestAnalyzeRequirementsStream:
    @pytest.mark.asyncio
    async def test_success_yields_test_points(self, monkeypatch):
        payload = json.dumps([{"module": "登录", "point": "密码错误提示"}], ensure_ascii=False)
        patch_httpx(monkeypatch, analyze_module, [FakeSSEResponse(sse(payload[:10], payload[10:]))])

        chunks = [chunk async for chunk in make_analyze_mixin().analyze_requirements_stream("需求")]

        assert chunks[-1]["message"] == "分析完成"
        assert chunks[-1]["data"] == [{"module": "登录", "point": "密码错误提示"}]

    @pytest.mark.asyncio
    async def test_unparsable_stream_returns_parse_error(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        patch_httpx(monkeypatch, analyze_module, [FakeSSEResponse(sse("完全不是 JSON"))])

        chunks = [chunk async for chunk in make_analyze_mixin().analyze_requirements_stream("需求")]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["message"] == "AI响应格式错误，无法解析"

    @pytest.mark.asyncio
    async def test_http_error_retries_then_succeeds(self, monkeypatch):
        payload = json.dumps([{"module": "M", "point": "P"}])
        responses = [httpx.ConnectError("boom"), FakeSSEResponse(sse(payload))]
        client = patch_httpx(monkeypatch, analyze_module, responses)

        chunks = [chunk async for chunk in make_analyze_mixin(max_retries=2).analyze_requirements_stream("需求")]

        assert chunks[-1]["data"] == [{"module": "M", "point": "P"}]
        assert len(client.stream_calls) == 2

    @pytest.mark.asyncio
    async def test_http_error_exhausted_returns_error(self, monkeypatch):
        patch_httpx(monkeypatch, analyze_module, [httpx.ConnectError("boom")])

        chunks = [chunk async for chunk in make_analyze_mixin().analyze_requirements_stream("需求")]

        assert chunks[-1]["error"] is True
        assert chunks[-1]["message"]

    @pytest.mark.asyncio
    async def test_unexpected_error_prefixes_message(self, monkeypatch):
        patch_httpx(monkeypatch, analyze_module, [ValueError("boom")])

        chunks = [chunk async for chunk in make_analyze_mixin().analyze_requirements_stream("需求")]

        assert chunks[-1]["message"].startswith("分析失败: ")
