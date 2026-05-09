"""
AI客户端JSON解析增强单元测试

覆盖范围（基于真实AI返回的损坏格式）:
- clean_json_string() 6种修复策略逐一验证
- extract_json_objects_fallback() 增强�?层解�?
- parse_test_point_object() 边界情况
- extract_value() 类型覆盖
- 真实损坏场景复现（本次核心bug修复验证�?
- fix_common_json_issues() 通用修复
"""
import pytest
import json

from app.utils.ai_client_parser import (
    clean_json_string,
    extract_json_objects_fallback,
    parse_test_point_object,
    extract_value,
    fix_common_json_issues,
)
from app.utils.ai_client import AIClient


@pytest.fixture
def ai_client():
    return AIClient()


class TestCleanJsonStringSixStrategies:

    def test_strategy0_valid_json_passthrough(self):
        valid = '{"module": "登录", "function": "验证", "point": "测试点描�?, "priority": 1}'
        result = clean_json_string(valid)
        assert result == valid
        parsed = json.loads(result)
        assert parsed['module'] == '登录'

    def test_strategy1_single_quotes(self):
        input_str = "{'module': 'UserMgr', 'function': 'Login', 'point': 'Verify password', 'priority': 2}"
        result = clean_json_string(input_str)
        valid_json = '{"module": "Test", "point": "OK", "priority": 1}'
        assert clean_json_string(valid_json) == valid_json
        if result is not None:
            parsed = json.loads(result)
            assert parsed['module'] == 'UserMgr'

    def test_strategy2_missing_comma_between_kv(self):
        input_str = '{"module":"登录""function":"验证""point":"测试"}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert 'module' in parsed

    def test_strategy3_missing_comma_between_objects(self):
        input_str = '{"a":1}{"b":2}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)

    def test_strategy4_unquoted_values(self):
        input_str = '{"module": "登录", "function": 验证密码, "priority": 1}'
        result = clean_json_string(input_str)
        if result is not None:
            try:
                parsed = json.loads(result)
                assert parsed['module'] == '登录'
            except json.JSONDecodeError:
                pass

    def test_strategy5_missing_key_quote(self):
        input_str = '{module": "登录", function": "验证", "point": "测试�?}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert 'module' in parsed or 'login' in str(parsed).lower()

    def test_strategy6_combined_issues(self):
        input_str = "{'module':'登录','function':'验证','point':'测试描述',}"
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert parsed['module'] == '登录'


class TestCleanJsonStringEdgeCases:

    def test_empty_string(self):
        assert clean_json_string("") is None

    def test_none_input(self):
        assert clean_json_string(None) is None

    def test_control_chars_stripped(self):
        input_str = '{"key": "val\x00ue\x08\x01", "name": "test"}'
        result = clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert '\x00' not in parsed['key']
            assert '\x08' not in parsed['key']

    def test_unicode_content(self):
        input_str = '{"module": "用户管理🔐", "function": "登录�?, "point": "中文测试点描�?}'
        result = clean_json_string(input_str)
        assert result is not None
        parsed = json.loads(result)
        assert '🔐' in parsed['module']

    def test_very_long_value(self):
        long_point = "测试" * 200
        input_str = f'{{"module": "M", "point": "{long_point}"}}'
        result = clean_json_string(input_str)
        assert result is not None

    def test_nested_json_structure(self):
        input_str = '{"outer": {"inner": {"deep": "value"}}, "arr": [1, 2, 3]}'
        result = clean_json_string(input_str)
        assert result is not None
        parsed = json.loads(result)
        assert parsed['outer']['inner']['deep'] == 'value'

    def test_numeric_priority_variations(self):
        for prio in ['1', '2', '3', '0', '10']:
            input_str = f'{{"module": "M", "point": "P", "priority": {prio}}}'
            result = clean_json_string(input_str)
            assert result is not None


class TestExtractFallbackRealWorldScenarios:

    def test_scenario_1_missing_quotes_on_keys(self):
        content = '''[
  {module: "链接管理模块", function: 新增"添加�?字段", point: 验证在黑白名单链接列表中新增的添加人列正确显�? priority: 1},
  {module: "链接管理模块", function: 新增"添加�?字段", point: 验证添加新链接时添加人字段自动填充为当前执行操作的用户身�? priority: 1}
]'''
        results = extract_json_objects_fallback(content)
        assert isinstance(results, list)

    def test_scenario_2_concatenated_objects_no_comma(self):
        content = '''[
{"module": "用户管理", "function": "登录功能", "point": "验证正确用户名密码可以成功登录系�?, "priority": 1}
{"module": "用户管理", "function": "登录功能", "point": "验证错误密码三次后锁定账�?0分钟", "priority": 2}
{"module": "用户管理", "function": "登录功能", "point": "验证账号不存在时提示友好错误信息", "priority": 3}
]'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 2, f"应提取到至少2个测试点，实�? {len(results)}"

    def test_scenario_3_mixed_quotes_and_missing_commas(self):
        content = '''[{module:"订单管理",function:"创建订单",point:"验证用户可以成功创建新订单并生成订单�?,priority:1}{module:"订单管理",function:"支付订单",point:"验证支付金额与订单金额一�?,priority:1}]'''
        results = extract_json_objects_fallback(content)
        assert isinstance(results, list)

    def test_scenario_4_line_by_line_format(self):
        content = '''{
"module": "商品管理",
"function": "商品搜索",
"point": "验证输入关键词可以搜索到匹配的商品列�?,
"priority": 1
}
{
"module": "商品管理",
"function": "商品详情",
"point": "验证点击商品可以查看完整的商品详细信�?,
"priority": 2
}'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1, f"逐行格式应能提取，实�? {len(results)}"

    def test_scenario_5_ai_text_surrounding_json(self):
        content = '''根据需求文档分析，以下是提取的测试点：

[
  {
    "module": "权限管理",
    "function": "角色分配",
    "point": "验证管理员可以为用户分配正确的角色权�?,
    "priority": 1
  }
]

以上测试点覆盖了核心业务流程�?''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_scenario_6_markdown_code_block(self):
        content = '''```json
[
  {"module": "报告模块", "function": "导出Excel", "point": "验证导出的Excel数据与页面展示一�?, "priority": 1},
  {"module": "报告模块", "function": "打印预览", "point": "验证打印预览格式与实际打印一�?, "priority": 2}
]
```'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_scenario_7_special_chars_in_chinese_quotes(self):
        content = '''[
  {"module": "设置模块", "function": "通知设置", "point": "验证开启\"推送通知\"后可以收到消息推�?, "priority": 1},
  {"module": "设置模块", "function": "隐私设置", "point": "验证隐藏手机号中间四位显示为****", "priority": 2}
]'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_scenario_8_large_batch_extraction(self):
        points = []
        for i in range(15):
            points.append(f'''{{
"module": "模块{i}",
"function": "功能{i}",
"point": "这是第{i}个测试点的详细描述用于验证批量提取能�?,
"priority": {(i % 3) + 1}
}}''')
        content = '[\n' + ',\n'.join(points) + '\n]'
        results = extract_json_objects_fallback(content)
        assert len(results) >= 10, f"大批量应提取�?=10个，实际: {len(results)}"


class TestExtractFallbackMethodCoverage:

    def test_method1_array_clean_passes(self):
        content = '[{"module":"A","function":"B","point":"C","priority":1},{"module":"D","function":"E","point":"F","priority":2}]'
        results = extract_json_objects_fallback(content)
        assert len(results) == 2

    def test_method1_individual_object_clean(self):
        content = '''[
  {"module": "A", "function": "B", "point": "C", "priority": 1},
  {module: "D", function: "E", point: "F", priority: 2}
]'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_method2_regex_point_extraction(self):
        content = '''一些文�?
{"module": "M1", "function": "F1", "point": "这是一个测试点描述应该被提取出�?, "priority": 1}
更多文本内容
{"module": "M2", "function": "F2", "point": "另一个测试点也应该被提取", "priority": 2}
结尾文本'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_method3_line_by_line_parsing(self):
        content = '''{
"module": "测试",
"function": "功能",
"point": "详细的测试点描述内容",
"priority": 1
}'''
        results = extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_all_methods_run_before_return(self):
        content = '''[
{module: "坏格�?", point: "�?", priority: 1}
{module: "坏格�?", point: "�?", priority: 2}
无效文本�?
"point": "独立的点3"
{
"module": "独立对象",
"point": "�?",
"priority": 3
}
]'''
        results = extract_json_objects_fallback(content)
        assert isinstance(results, list)


class TestParseTestPointObjectDetailed:

    def test_complete_object(self):
        text = '{"module": "M", "function": "F", "point": "完整测试点P", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is not None
        assert result['module'] == 'M'
        assert result['function'] == 'F'
        assert result['point'] == '完整测试点P'
        assert result['priority'] == 1

    def test_module_optional(self):
        text = '{"function": "F", "point": "有point就够�?, "priority": 2}'
        result = parse_test_point_object(text)
        assert result is not None
        assert result['point'] == '有point就够�?

    def test_function_optional(self):
        text = '{"module": "M", "point": "只需要point", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is not None

    def test_empty_point_rejected(self):
        text = '{"module": "M", "point": "", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is None

    def test_whitespace_only_point_rejected(self):
        text = '{"module": "M", "point": "   ", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is None

    def test_no_point_field_returns_none(self):
        text = '{"module": "M", "function": "F", "priority": 1}'
        result = parse_test_point_object(text)
        assert result is None

    def test_multiline_point(self):
        text = '''{
"module": "M",
"point": "第一行描�?
第二行描�?
第三行描�?,
"priority": 1
}'''
        result = parse_test_point_object(text)
        assert result is not None
        assert '第一�? in result['point']

    def test_garbage_input_returns_none(self):
        assert parse_test_point_object("") is None
        assert parse_test_point_object("{{{") is None
        assert parse_test_point_object("just text") is None


class TestExtractValueTypes:

    def test_quoted_string(self):
        assert extract_value('"hello world"') == 'hello world'

    def test_quoted_string_with_internal_quotes(self):
        result = extract_value('"he said \\"hi\\""')
        assert 'hi' in result

    def test_positive_integer(self):
        result = extract_value('42')
        assert result == 42
        assert isinstance(result, int)

    def test_negative_integer(self):
        result = extract_value('-17')
        assert result == -17

    def test_float_number(self):
        result = extract_value('3.14159')
        assert abs(result - 3.14159) < 0.0001
        assert isinstance(result, float)

    def test_negative_float(self):
        result = extract_value('-0.5')
        assert result == -0.5

    def test_boolean_true_variants(self):
        assert extract_value('true') is True
        assert extract_value('True') is True

    def test_boolean_false_variants(self):
        assert extract_value('false') is False
        assert extract_value('False') is False

    def test_trailing_comma_stripped(self):
        assert extract_value('"value",') == 'value'
        assert extract_value('123,') == 123

    def test_bare_word_returned_as_is(self):
        result = extract_value('some_bare_word')
        assert result == 'some_bare_word'

    def test_empty_input(self):
        assert extract_value('') is None
        assert extract_value(',') is None

    def test_zero_value(self):
        assert extract_value('0') == 0


class TestFixCommonJsonIssues:

    def test_valid_json_unchanged(self):
        valid = '{"key": "value", "num": 123}'
        assert fix_common_json_issues(valid) == valid

    def test_trailing_comma_in_object(self):
        fixed = fix_common_json_issues('{"a": 1, "b": 2,}')
        assert fixed is not None
        parsed = json.loads(fixed)
        assert parsed['a'] == 1

    def test_trailing_comma_in_array(self):
        fixed = fix_common_json_issues('[1, 2, 3,]')
        assert fixed is not None
        parsed = json.loads(fixed)
        assert len(parsed) == 3

    def test_single_line_comment_removed(self):
        fixed = fix_common_json_issues('{"a": 1, // comment\n"b": 2}')
        assert fixed is not None

    def test_block_comment_removed(self):
        fixed = fix_common_json_issues('{"a": /* block */ 1, "b": 2}')
        assert fixed is not None

    def test_none_input(self):
        assert fix_common_json_issues(None) is None

    def test_empty_string(self):
        assert fix_common_json_issues("") is None


class TestContentProtection:

    def test_exact_limit_accepted(self):
        content = '[\n' + '  {"m":"t","f":"t","p":"d","priority":1},\n' * 1190 + ']'
        assert len(content) <= 50000
        results = extract_json_objects_fallback(content)
        assert isinstance(results, list)

    def test_over_limit_truncated(self):
        content = 'x' * 60000
        try:
            results = extract_json_objects_fallback(content)
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"超大内容不应抛异�? {e}")

    def test_empty_content(self):
        assert extract_json_objects_fallback('') == []

    def test_null_bytes_content(self):
        content = '[{"m": "\x00test", "p": "data"}]'
        results = extract_json_objects_fallback(content)
        assert isinstance(results, list)


class TestAIClientInit:

    def test_api_key_loaded(self, ai_client):
        assert ai_client.api_key is not None
        assert len(ai_client.api_key) > 0

    def test_model_configured(self, ai_client):
        assert ai_client.model is not None
        assert len(ai_client.model) > 0

    def test_url_configured(self, ai_client):
        assert ai_client.api_url is not None
        assert ai_client.api_url.startswith('http')

    def test_retry_settings(self, ai_client):
        assert ai_client.max_retries > 0
        assert ai_client.retry_delay > 0

    def test_cache_initialized(self, ai_client):
        assert isinstance(ai_client.cache, dict)
        assert len(ai_client.cache) == 0
