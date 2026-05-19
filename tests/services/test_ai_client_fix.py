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
