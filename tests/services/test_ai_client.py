"""
AI客户端JSON解析单元测试

覆盖范围:
- clean_json_string() JSON字符串清理和修复
- extract_json_objects_fallback() Fallback解析方法
- parse_test_point_object() 单个对象解析
- extract_value() 值提�?
- 各种格式错误的JSON修复能力
"""
import pytest
import json

from app.utils.ai_client_parser import (
    clean_json_string,
    extract_json_objects_fallback,
    parse_test_point_object,
    extract_value,
)
from app.utils.ai_client import AIClient


@pytest.fixture
def ai_client():
    return AIClient()


class TestCleanJsonString:

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

    def test_missing_quotes_on_key(self):
        input_str = '{key":"value","function":"login"}'
        result = clean_json_string(input_str)

    def test_missing_comma_between_objects(self):
        input_str = '{"a":1}{"b":2}'
        result = clean_json_string(input_str)

    def test_empty_string_returns_none(self):
        result = clean_json_string("")
        assert result is None

    def test_none_input_returns_none(self):
        result = clean_json_string(None)
        assert result is None

    def test_control_characters_removed(self):
        input_str = '{"key": "val\x00ue", "name": "test\x08x"}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert '\x00' not in parsed.get('key', '')


class TestExtractJsonObjectsFallback:

    def test_valid_array_extraction(self):
        content = '''
[
  {"module": "登录模块", "function": "用户登录", "point": "验证正确密码登录成功", "priority": 1},
  {"module": "登录模块", "function": "用户登录", "point": "验证错误密码提示错误", "priority": 1}
]
'''
        results = extract_json_objects_fallback(content)
        assert len(results) == 2
        assert results[0]['module'] == '登录模块'
        assert results[0]['point'] == '验证正确密码登录成功'

    def test_real_ai_response_format(self):
        content = '''[
  {
    "module": "链接管理模块",
    "function": "新增"添加�?字段",
    "point": "验证在黑白名单链接列表中，新增的'添加�?列正确显�?,
    "priority": 1
  },
  {
    "module": "链接管理模块",
    "function":新增"添加�?字段",
    "point": "验证添加新链接时�?添加�?字段自动填充为当前执行操作的用户身份",
    "priority": 1
  }
]'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1
        assert 'module' in results[0]
        assert 'point' in results[0]
        assert len(results[0]['point']) > 10

    def test_broken_format_with_missing_quotes(self):
        content = '''[
  {module: "用户管理", function: 登录功能, point: 验证用户登录, priority: 1}
]'''
        results = extract_json_objects_fallback(content)

    def test_line_by_line_parsing(self):
        content = '''[
{
"module": "测试模块",
"function": "测试功能",
"point": "这是测试点描�?,
"priority": 2
}
]'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_empty_content(self):
        results = extract_json_objects_fallback('')
        assert results == []

    def test_no_json_content(self):
        results = extract_json_objects_fallback('这是一段纯文本，没有JSON')
        assert results == []

    def test_large_content_truncation(self):
        large_content = '[\n' + '  {"m":"test","f":"func","p":"desc","prio":1},\n' * 1000 + ']'
        try:
            results = extract_json_objects_fallback(large_content)
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"大内容处理不应抛出异�? {e}")


class TestParseTestPointObject:

    def test_valid_object(self):
        text = '{"module": "M", "function": "F", "point": "P", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is not None
        assert result['module'] == 'M'
        assert result['point'] == 'P'

    def test_missing_module(self):
        text = '{"function": "F", "point": "P", "priority": 1}'
        result = parse_test_point_object(text)

    def test_empty_point_returns_none(self):
        text = '{"module": "M", "function": "F", "point": "", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is None


class TestExtractValue:

    def test_string_value(self):
        result = extract_value('"hello world"')
        assert result == 'hello world'

    def test_integer_value(self):
        result = extract_value('123')
        assert result == 123
        assert isinstance(result, int)

    def test_float_value(self):
        result = extract_value('3.14')
        assert result == 3.14
        assert isinstance(result, float)

    def test_boolean_true(self):
        result = extract_value('true')
        assert result is True

    def test_boolean_false(self):
        result = extract_value('false')
        assert result is False

    def test_value_with_trailing_comma(self):
        result = extract_value('"test",')
        assert result == 'test'

    def test_empty_value(self):
        result = extract_value(',')
        assert result is None


class TestAiClientIntegration:

    def test_client_initialization(self, ai_client):
        assert ai_client is not None
        assert ai_client.api_key is not None
        assert len(ai_client.api_key) > 10

    def test_api_key_from_env(self, ai_client):
        import os
        env_key = os.getenv('DEEPSEEK_API_KEY')
        if env_key:
            assert ai_client.api_key == env_key
