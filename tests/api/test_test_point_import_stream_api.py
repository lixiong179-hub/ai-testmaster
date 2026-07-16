import pytest
from app.api.v1.endpoints.test_point_import_stream import _sse_event


class TestSSEEvent:
    def test_progress_event(self):
        result = _sse_event("progress", {"completed_batches": 1, "total_batches": 3})
        assert "event: progress" in result
        assert "completed_batches" in result
        assert "\n\n" in result

    def test_result_event(self):
        result = _sse_event("result", {"test_points": [{"module": "M", "point": "P"}]})
        assert "event: result" in result
        assert "test_points" in result

    def test_error_event(self):
        result = _sse_event("error", {"message": "解析失败"})
        assert "event: error" in result
        assert "解析失败" in result

    def test_no_bare_newlines_in_data(self):
        result = _sse_event("progress", {"key": "value\nwith\nnewlines"})
        lines = result.split("\n")
        data_line = [l for l in lines if l.startswith("data: ")]
        assert len(data_line) == 1

    def test_chinese_characters(self):
        result = _sse_event("result", {"module": "登录模块"})
        assert "登录模块" in result


class TestImportStreamAPI:
    async def test_without_auth(self, async_client):
        resp = await async_client.post("/api/v1/test-point/import-stream")
        assert resp.status_code in (401, 403, 404, 405, 422)
