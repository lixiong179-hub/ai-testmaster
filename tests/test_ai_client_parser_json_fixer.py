"""ai_client_parser JSON 容错解析 - JS 表达式清理测试

测试范围:
    - strip_js_string_methods: JS 字符串方法调用清理（repeat/padEnd/concat 等）
    - parse_ai_json_response: 含 JS 表达式的非法 JSON 能解析成功
    - 回归: 合法 JSON 不受影响
    - _build_prompt: 包含禁 JS 表达式约束文案

对应 BUG 11: AI 误产 "a".repeat(500) 当 JSON 值导致解析失败 → 0 用例
"""
import pytest

from app.utils.ai_client_parser import (
    parse_ai_json_response,
    strip_js_string_methods,
)


class TestStripJsStringMethods:
    """strip_js_string_methods: JS 字符串方法调用清理"""

    @pytest.mark.parametrize("raw,expected", [
        ('"a".repeat(500)', '"a"'),
        ('"test".repeat(3)', '"test"'),
        ('"x".padEnd(100, "0")', '"x"'),
        ('"x".padStart(5, "-")', '"x"'),
        ('"a".concat("b", "c")', '"a"'),
        ('"hello".slice(0, 3)', '"hello"'),
        ('"hello".substring(1)', '"hello"'),
        ('"a-b".replace("-", "_")', '"a-b"'),
        ('"a" .repeat(5)', '"a"'),
        ('"a".repeat (5)', '"a"'),
    ])
    def test_single_method_call(self, raw: str, expected: str) -> None:
        assert strip_js_string_methods(raw) == expected

    def test_chained_calls(self) -> None:
        """链式调用逐层剥离"""
        assert strip_js_string_methods('"a".repeat(2).repeat(3)') == '"a"'

    def test_in_json_value_position(self) -> None:
        """JS 表达式在 JSON 值位置被清理"""
        raw = '{"input_value": "a".repeat(500)}'
        cleaned = strip_js_string_methods(raw)
        assert '"a".repeat' not in cleaned
        assert '"a"' in cleaned

    def test_no_quotes_returns_unchanged(self) -> None:
        assert strip_js_string_methods("no quotes here") == "no quotes here"

    def test_empty_string(self) -> None:
        assert strip_js_string_methods("") == ""

    def test_legal_json_unchanged(self) -> None:
        """合法 JSON 不受影响（含 repeat 字样但非方法调用）"""
        raw = '{"a": "repeat", "b": "hello.world"}'
        assert strip_js_string_methods(raw) == raw

    def test_key_named_repeat_not_affected(self) -> None:
        """JSON key repeat 不被误伤"""
        raw = '{"repeat": 5}'
        assert strip_js_string_methods(raw) == raw


class TestParseAiJsonResponseWithJsExpressions:
    """parse_ai_json_response: 含 JS 表达式的非法 JSON 解析"""

    def test_input_value_with_repeat(self) -> None:
        raw = '{"cases": [{"title": "T1", "input_value": "a".repeat(500)}]}'
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["input_value"] == "a"

    def test_expected_result_with_padend(self) -> None:
        raw = '{"cases": [{"title": "T1", "expected_result": "x".padEnd(100, "0")}]}'
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["expected_result"] == "x"

    def test_js_expression_with_trailing_comma(self) -> None:
        """JS 表达式 + 尾逗号组合"""
        raw = '{"cases": [{"title": "T1", "input_value": "a".repeat(5),}],}'
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["input_value"] == "a"

    def test_js_expression_in_fenced_block(self) -> None:
        """JS 表达式在 markdown 代码块内也能解析"""
        raw = '```json\n{"cases": [{"title": "T1", "input_value": "a".repeat(3)}]}\n```'
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["input_value"] == "a"

    def test_multiple_js_expressions(self) -> None:
        """同一 JSON 含多处 JS 表达式"""
        raw = (
            '{"cases": [{"title": "T1", "input_value": "a".repeat(3),'
            '"expected_result": "x".padEnd(10, "0")}]}'
        )
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["input_value"] == "a"
        assert result["cases"][0]["expected_result"] == "x"

    def test_legal_json_regression(self) -> None:
        """回归: 合法 JSON 仍正常解析"""
        raw = '{"cases": [{"title": "T1", "input_value": "normal_text"}]}'
        result = parse_ai_json_response(raw)
        assert result is not None
        assert result["cases"][0]["input_value"] == "normal_text"

    def test_empty_input_regression(self) -> None:
        """回归: 空输入返回 None"""
        assert parse_ai_json_response("") is None
        assert parse_ai_json_response("   ") is None


class TestPromptForbidsJsExpressions:
    """_build_prompt 应包含禁 JS 表达式约束"""

    def test_prompt_contains_no_js_rule(self) -> None:
        from app.services.url_driven._prompt_mixin import (
            PromptMixin,
            _NO_JS_EXPRESSION_RULE,
        )
        from app.services.url_driven.site_explorer import PageSnapshot

        host = PromptMixin()
        snapshot = PageSnapshot(
            url="https://example.com",
            title="Example",
            elements=[{
                "role": "textbox",
                "name": "搜索",
                "locator": "get_by_role('textbox', name='搜索')",
            }],
            forms=[],
            navigation=[],
            is_login_page=False,
            screenshot_path=None,
            captured_at="2026-06-29T00:00:00Z",
        )
        test_point = {"test_point_type": "search", "related_elements": []}
        prompt = host._build_prompt(test_point, snapshot, None)
        assert _NO_JS_EXPRESSION_RULE in prompt
        assert "repeat" in prompt
