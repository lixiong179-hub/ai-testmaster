"""B6c 前置护栏：`link_fetcher` 三处拆分前后的行为锁定。

覆盖 JSON 认证失败探测（含嵌套与列表上限）、`fetch_content` 的 Content-Type 分派与
HTTP 状态映射、HTML 原型解析（标题/导航/表格/解析失败兜底）。
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.services.link_fetcher import LinkFetcherService


@pytest.fixture()
def service():
    svc = LinkFetcherService(timeout=5)
    svc.session = MagicMock()
    return svc


def _response(text="", content_type="text/plain", status_code=200, headers=None):
    resp = MagicMock()
    resp.text = text
    resp.headers = {"Content-Type": content_type} if headers is None else headers
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


class TestDetectAuthFailureInJson:
    @pytest.mark.parametrize(
        "data",
        [
            {"error": "Unauthorized access"},
            {"errors": ["请先登录"]},
            {"code": 401},
            {"code": "403"},
            {"status": "token expired"},
            {"statusCode": "invalid token"},
        ],
    )
    def test_top_level_hits(self, service, data):
        assert service._detect_auth_failure_in_json(data) is True

    def test_status_code_only_mapped_for_code_field(self, service):
        # 既有口径：401/403 的数值判定只认 `code` 字段，`statusCode`/`status` 仅走关键词
        assert service._detect_auth_failure_in_json({"statusCode": "401"}) is False
        assert service._detect_auth_failure_in_json({"status": 401}) is False

    def test_nested_dict_and_list(self, service):
        assert service._detect_auth_failure_in_json({"data": [{"meta": {"error": "unauthorized"}}]}) is True

    def test_list_scan_limited_to_ten(self, service):
        # 第 11 个元素不参与扫描（性能护栏，避免超大响应全量递归）
        payload = [{}] * 10 + [{"error": "unauthorized"}]
        assert service._detect_auth_failure_in_json(payload) is False

    @pytest.mark.parametrize("data", [{"code": 200}, {"error": "ok"}, "plain", 42, None])
    def test_non_hits(self, service, data):
        assert service._detect_auth_failure_in_json(data) is False

    def test_plain_text_token_in_non_error_field_ignored(self, service):
        assert service._detect_auth_failure_in_json({"message": "unauthorized access"}) is False


class TestProcessJson:
    def test_valid_json_formatted(self, service):
        ok, content, kind = service._process_json('{"b": 1, "a": 2}')
        assert ok is True
        assert kind == "json"
        assert '"a": 2' in content

    def test_auth_failure_detected(self, service):
        ok, content, msg = service._process_json('{"error": "unauthorized"}')
        assert (ok, content) == (False, "")
        assert "认证失败" in msg

    def test_invalid_json_falls_back_to_text(self, service):
        ok, content, kind = service._process_json("{not json")
        assert (ok, kind) == (True, "text")
        assert content == "{not json"

    def test_long_text_truncated(self, service):
        ok, content, _ = service._process_json("x" * 6000)
        assert ok is True
        assert len(content) == 5000


class TestFetchContentDispatch:
    @pytest.mark.parametrize(
        ("content_type", "expected_method"),
        [
            ("application/json; charset=utf-8", "_process_json"),
            ("text/html; charset=utf-8", "_process_html"),
            ("text/plain", "_process_html"),
            ("text/markdown", "_process_markdown"),
            ("application/octet-stream", "_process_auto"),
        ],
    )
    def test_dispatch_by_content_type(self, service, content_type, expected_method):
        service.session.get.return_value = _response("body", content_type)
        with patch.object(service, expected_method, return_value=(True, "x", "y")) as mock_process:
            with patch.object(service, "_process_auto", return_value=(True, "x", "y")) as mock_auto:
                result = service.fetch_content("https://example.com/a")
        assert result == (True, "x", "y")
        assert mock_process.called or (expected_method == "_process_auto" and mock_auto.called)

    def test_markdown_by_suffix_without_content_type(self, service):
        service.session.get.return_value = _response("body", "application/octet-stream")
        with patch.object(service, "_process_markdown", return_value=(True, "md", "markdown")) as mock_md:
            assert service.fetch_content("https://example.com/readme.md") == (True, "md", "markdown")
        assert mock_md.called

    @pytest.mark.parametrize(
        ("status_code", "expected_msg"),
        [
            (401, "认证失败，请检查用户名密码或Token"),
            (403, "权限不足，无法访问该链接"),
            (404, "资源不存在 (404)"),
            (500, "HTTP错误: 500"),
        ],
    )
    def test_http_error_mapping(self, service, status_code, expected_msg):
        resp = _response(status_code=status_code)
        error = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = error
        service.session.get.return_value = resp
        assert service.fetch_content("https://example.com") == (False, "", expected_msg)

    def test_timeout(self, service):
        service.session.get.side_effect = requests.exceptions.Timeout()
        assert service.fetch_content("https://example.com") == (False, "", "请求超时")

    def test_connection_error(self, service):
        service.session.get.side_effect = requests.exceptions.ConnectionError()
        assert service.fetch_content("https://example.com") == (False, "", "连接失败，请检查链接地址")

    def test_unexpected_exception(self, service):
        service.session.get.side_effect = RuntimeError("boom")
        assert service.fetch_content("https://example.com") == (False, "", "获取内容失败")


class TestFetchAndParseUIMockup:
    def test_returns_error_when_fetch_fails(self, service):
        # 既有行为：失败时第三个返回值取的是 fetch_content 的「内容」段（空串），
        # 而非其错误信息段；此处先锁定现状，不在本次拆分中改动语义
        with patch.object(service, "fetch_content", return_value=(False, "", "认证失败")):
            ok, desc, msg = service.fetch_and_parse_ui_mockup("https://x")
        assert (ok, desc, msg) == (False, {}, "")

    def test_html_extracts_title_links_tables(self, service):
        html = """
        <html><head><title>登录页</title></head>
        <body>
          <a href="/order">订单</a><a href="">空文本</a><a>无链接</a>
          <table><tr><th>姓名</th><td>张三</td></tr><tr></tr></table>
        </body></html>
        """
        with patch.object(service, "fetch_content", return_value=(True, html, "html")):
            ok, desc, msg = service.fetch_and_parse_ui_mockup("https://x")
        assert (ok, msg) == (True, "")
        assert desc["title"] == "登录页"
        assert desc["pages"] == [{"text": "订单", "href": "/order"}]
        assert desc["tables"] == [[["姓名", "张三"]]]
        assert "页面标题: 登录页" in desc["summary"]

    def test_html_without_links_or_tables(self, service):
        with patch.object(service, "fetch_content", return_value=(True, "<html><title>T</title></html>", "html")):
            ok, desc, _ = service.fetch_and_parse_ui_mockup("https://x")
        assert ok is True
        assert desc["pages"] == []
        assert "tables" not in desc

    def test_non_html_uses_content_prefix(self, service):
        with patch.object(service, "fetch_content", return_value=(True, "y" * 2000, "json")):
            ok, desc, _ = service.fetch_and_parse_ui_mockup("https://x")
        assert ok is True
        assert desc["summary"] == "y" * 1000

    def test_empty_content_summary(self, service):
        with patch.object(service, "fetch_content", return_value=(True, "", "json")):
            _, desc, _ = service.fetch_and_parse_ui_mockup("https://x")
        assert desc["summary"] == "无内容"

    def test_html_parse_failure_falls_back_to_content_prefix(self, service):
        with patch.object(service, "fetch_content", return_value=(True, "a" * 800, "html")):
            with patch("app.services.link_fetcher.ui_mixin.BeautifulSoup", side_effect=RuntimeError("bad html")):
                ok, desc, _ = service.fetch_and_parse_ui_mockup("https://x")
        assert ok is True
        assert desc["summary"] == "a" * 500
