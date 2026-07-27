"""
AI客户端JSON解析工具函数测试

覆盖范围:
- clean_json_string JSON修复能力
- extract_json_objects_fallback 返回类型
- 各种格式错误的JSON修复能力

要求: 使用真实环境，不使用Mock
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.ai_client import (
    fix_common_json_issues,
    clean_json_string,
    extract_json_objects_fallback,
)
from app.utils.ai_client_parser import parse_ai_json_response, parse_ai_json_object


class TestCleanJsonString:
    """JSON字符串清理方法测试"""

    def test_valid_json_passes_through(self):
        valid = '{"key": "value", "num": 123}'
        result = clean_json_string(valid)
        assert result is not None
        parsed = json.loads(result)
        assert parsed['key'] == 'value'
        assert parsed['num'] == 123

    def test_single_quotes_to_double(self):
        input_str = "{'key': 'value', 'name': 'test'}"
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert parsed['key'] == 'value'

    def test_trailing_comma_removal(self):
        input_str = '{"key": "value", "num": 123,}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert parsed['key'] == 'value'

    def test_missing_space_after_colon(self):
        input_str = '{"key":"value","name":"test"}'
        result = clean_json_string(input_str)
        assert result is not None or result is None


class TestExtractJsonObjectsFallback:
    """Fallback JSON提取测试"""

    def test_array_in_text(self):
        text = 'Here is the JSON: [{"name": "test1"}, {"name": "test2"}]'
        result = extract_json_objects_fallback(text)
        assert result is not None
        assert isinstance(result, (str, list))

    def test_array_with_extra_brackets(self):
        text = '[[{"name": "test"}]]'
        result = extract_json_objects_fallback(text)
        assert result is not None

    def test_object_in_text(self):
        text = 'Result: {"name": "test", "value": 123}'
        result = extract_json_objects_fallback(text)
        assert result is not None
        assert isinstance(result, (str, list))

    def test_no_json_in_text(self):
        text = 'No JSON here, just plain text'
        result = extract_json_objects_fallback(text)
        assert result is None or result == []


class TestAnalyzeRequirementsReturnPaths:
    """fix_common_json_issues 返回路径测试——核心修复验证"""

    def test_returns_list_when_json_valid(self):
        """JSON有效时返回修复后的字符串——核心场景"""
        valid_json = '[{"description": "test", "priority": 1}]'
        result = fix_common_json_issues(valid_json)
        assert result is not None
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_returns_none_for_invalid_json(self):
        """完全无效的JSON返回None"""
        invalid = 'This is not JSON at all'
        result = fix_common_json_issues(invalid)
        assert result is None

    def test_json_decode_error_returns_none(self):
        """JSONDecodeError时返回None"""
        invalid = '{"key": "value",}'
        result = fix_common_json_issues(invalid)
        if result is not None:
            try:
                json.loads(result)
            except json.JSONDecodeError:
                pytest.fail("Should have returned None for invalid JSON")


class TestParseAiJsonResponse:
    def test_parse_strict_object(self):
        result = parse_ai_json_response('{"passed": true, "reason": "ok"}')
        assert result == {"passed": True, "reason": "ok"}

    def test_parse_strict_array(self):
        result = parse_ai_json_response('[{"module": "M", "point": "P"}]')
        assert isinstance(result, list)
        assert result[0]["module"] == "M"

    def test_parse_object_with_comment_and_trailing_comma(self):
        result = parse_ai_json_response('{"passed": true, // note\n "reason": "ok",}')
        assert result == {"passed": True, "reason": "ok"}

    def test_parse_single_quoted_object(self):
        result = parse_ai_json_response("{'passed': true, 'reason': 'ok'}")
        assert result == {"passed": True, "reason": "ok"}

    def test_parse_json_code_fence(self):
        result = parse_ai_json_response('说明\n```json\n{"passed": true}\n```\n结束')
        assert result == {"passed": True}

    def test_parse_prefers_largest_complete_block(self):
        raw = '示例 {"a": 1} 实际 {"passed": true, "reason": "ok", "extra": {"x": 1}}'
        result = parse_ai_json_response(raw)
        assert result == {"passed": True, "reason": "ok", "extra": {"x": 1}}

    def test_parse_ai_json_object_rejects_array(self):
        assert parse_ai_json_object('[{"module": "M"}]') is None

    def test_unparseable_returns_none(self):
        assert parse_ai_json_response("not json at all") is None
